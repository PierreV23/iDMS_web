#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" > /dev/null 2>&1 && pwd )"

source activate idms_web
export FLASK_INSTANCE_PATH=${DIR}/../instance
export FLASK_APP="idms.web:create_app()"
PORT=55${UID: -3}
echo RUN on $PORT
flask --debug run --host=0.0.0.0 --port=$PORT --with-threads --no-reload
conda deactivate
