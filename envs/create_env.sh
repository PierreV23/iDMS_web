#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" > /dev/null 2>&1 && pwd )"

conda env list | grep idms_web
if [ $? -ne 0 ] ; then
  echo "Environment 'idms_web' not found. Creating from envs/idms_web.yaml..."
  mamba env create -f ${DIR}/../envs/idms_web.yaml -q
else
  echo "Update 'idms_web' environment from envs/idms_web.yaml..."
  mamba env update -f ${DIR}/../envs/idms_web.yaml -q
fi
source activate idms_web

pip install --extra-index-url https://gitlab.rivm.nl/api/v4/projects/4682/packages/pypi/simple --no-build-isolation -e .