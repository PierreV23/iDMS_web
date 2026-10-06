FROM mambaorg/micromamba:1.5 AS base

USER root

# Install basic network/debug utilities using apt
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    bash \
    && rm -rf /var/lib/apt/lists/*

USER $MAMBA_USER

# Copy baked-in uWSGI configuration
COPY --chown=$MAMBA_USER:$MAMBA_USER uwsgi.ini /etc/uwsgi/uwsgi.ini
COPY --chown=$MAMBA_USER:$MAMBA_USER envs/idms_web.yaml /tmp/idms_web.yaml

RUN micromamba install -y -n base -f /tmp/idms_web.yaml && \
    micromamba clean --all --yes

# Activate environment for subsequent RUN commands
ARG MAMBA_DOCKERFILE_ACTIVATE=1
ARG BRANCH=master
ARG PORT=3456

ENV PORT=${PORT}
ENV FLASK_INSTANCE_PATH=/idms_web/instance

RUN pip install --extra-index-url https://gitlab.rivm.nl/api/v4/projects/4682/packages/pypi/simple "git+https://gitlab.rivm.nl/bioinformatics/ngsweb.git@${BRANCH}"

WORKDIR /idms_web

# Set the locale
# RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
#     locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# When image is run, run the code with the environment
# activated:
# SHELL ["/bin/bash", "-c"]
ENTRYPOINT [ "/usr/local/bin/_entrypoint.sh", "sh", "-c", "/opt/conda/bin/uwsgi --home /opt/conda --ini /etc/uwsgi/uwsgi.ini --http 0.0.0.0:${PORT}"]

