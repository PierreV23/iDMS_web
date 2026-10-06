import logging
import atexit
import os
import tempfile

from flask import Blueprint

logger = logging.getLogger(__name__)

def init_workdir(app, subdirs=[]):
    workdir = app.config.get('TMPDIR')
    if workdir is None:
        workdir = tempfile.TemporaryDirectory().name
    workdir = os.path.abspath(workdir)
    bp = Blueprint(
        'workdir',
        __name__,
        workdir,
        '/workdir'
    )
    logger.info(f'Temporary storage location is {workdir}')
    app.register_blueprint(bp)
    for subdir in subdirs:
        os.makedirs(os.path.join(workdir, subdir), exist_ok=True)
    app.workdir = workdir
    