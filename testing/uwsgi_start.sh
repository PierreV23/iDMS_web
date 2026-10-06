#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" > /dev/null 2>&1 && pwd )"

source activate idms_web
if [ $? -ne 0 ] ; then
mamba env create -f ${DIR}/../envs/idms_web.yaml -q
source activate idms_web
fi

pip install --extra-index-url https://gitlab.rivm.nl/api/v4/projects/4682/packages/pypi/simple --no-build-isolation -e .

PORT=5${UID: -3}

echo Listening on port ${PORT}
export FLASK_INSTANCE_PATH=${DIR}/../instance
uwsgi --http :${PORT} --ini  ${DIR}/uwsgi.test.ini --metrics-dir metrics
source deactivate
