"""database connection classes with pre-ping and auto-reconnect logic"""

import atexit
import logging
import threading

import psycopg2
from flask import current_app
from flask_login import current_user
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def my_env():
    """Return environment the current_user is logged in to or None if not set."""
    if hasattr(current_user, "environment"):
        return current_user.environment
    return None


class ICATDBUnavailableException(Exception):
    pass


class DBConnection:
    def __init__(self, dbpool):
        self._pool = dbpool
        self._conn = None

    def _get_healthy_conn(self):
        """Fetch a connection from the pool and verify it's alive (pre-ping)."""
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts:
            conn = self._pool.getconn()
            try:
                # Pre-ping: test connection health
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1;")
                return conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                logger.warning(
                    f"Discarding stale database connection from pool: {e}"
                )
                # Inform the pool to permanently close and remove this broken connection
                self._pool.putconn(conn, close=True)
                attempts += 1

        raise ICATDBUnavailableException(
            "Failed to acquire a healthy database connection after multiple attempts."
        )

    def sql(self, statement, params=None, retry_on_failure=True):
        """Execute query with automatic retry once if connection drops mid-execution."""
        try:
            with self as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(statement, params or ())
                    if cursor.description:  # True if the statement returns rows
                        return cursor.fetchall()
                    return []
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            # If the query failed because the connection dropped mid-request
            if retry_on_failure:
                logger.warning(
                    f"Database connection lost during query execution. Retrying... Error: {e}"
                )
                return self.sql(statement, params, retry_on_failure=False)
            raise

    def __enter__(self):
        self._conn = self._get_healthy_conn()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            try:
                if exc_type is not None:
                    self._conn.rollback()
                    # If exception is a connection-level drop, close connection instead of returning to pool
                    if issubclass(
                        exc_type,
                        (psycopg2.OperationalError, psycopg2.InterfaceError),
                    ):
                        self._pool.putconn(self._conn, close=True)
                        self._conn = None
                        return
                else:
                    self._conn.commit()
            except Exception as e:
                logger.error(
                    f"Error committing/rolling back transaction: {e}"
                )
                self._pool.putconn(self._conn, close=True)
                self._conn = None
                return

            # Return healthy connection back to the pool
            self._pool.putconn(self._conn)
            self._conn = None


class DBPools:

    def __init__(self, db_key):
        self._db_key = db_key
        self._pools = {}
        self._lock = threading.Lock()

    def init_app(self, app):
        """Register pool cleanup when Python process terminates."""
        atexit.register(self.close_all_pools)

    def close_all_pools(self, exception=None):
        """Close all active psycopg2 connection pools safely."""
        with self._lock:
            for db_pool in self._pools.values():
                if db_pool and not db_pool.closed:
                    db_pool.closeall()
            self._pools.clear()

    def startpool(self, env):
        with self._lock:
            if env in self._pools:
                return

            env_params = current_app.config["IRODS_ENVS"].get(env)
            if not env_params or self._db_key not in env_params:
                raise ICATDBUnavailableException(
                    f"Configuration missing for env={env}"
                )

            db_connect = env_params[self._db_key]

            if isinstance(db_connect, dict):
                pool_inst = pool.ThreadedConnectionPool(5, 50, **db_connect)
            else:
                pool_inst = pool.ThreadedConnectionPool(
                    5, 50, dsn=db_connect
                )

            self._pools[env] = pool_inst

    def connection(self):
        env = my_env()
        if not env:
            raise ICATDBUnavailableException(
                "No environment set for current user."
            )

        if env not in self._pools:
            self.startpool(env)

        return DBConnection(self._pools[env])


jobs_db = DBPools("jobs_db")
search_db = DBPools("search_db")