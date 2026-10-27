#!/usr/bin/env bash
exec irods-dev << 'EOSCRIPT'
nc -zv -w 3 res-irods91.researchlumc.nl 1247 || { echo "iRODS VM not reachable"; exit 1; }
flask --debug run --host=0.0.0.0 --port=5000 --with-threads
EOSCRIPT
