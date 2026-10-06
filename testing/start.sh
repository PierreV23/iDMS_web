#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" > /dev/null 2>&1 && pwd )"

source activate idms_web
if [ $? -ne 0 ] ; then
  echo "Environment 'idms_web' not found. Creating from envs/idms_web.yaml..."
  mamba env create -f ${DIR}/../envs/idms_web.yaml -q
  source activate idms_web
fi

pip install --extra-index-url https://gitlab.rivm.nl/api/v4/projects/4682/packages/pypi/simple --no-build-isolation -e .

export FLASK_INSTANCE_PATH=${DIR}/../instance
export FLASK_APP="idms.web:create_app()"

PORT=55${UID: -3}
echo RUN on $PORT
flask --debug run --host=0.0.0.0 --port=$PORT --with-threads
conda deactivate
