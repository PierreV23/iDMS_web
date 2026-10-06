# iDMS_web

[![fair-software.eu](https://img.shields.io/badge/fair--software.eu-%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8B%20%20%E2%97%8B%20%20%E2%97%8B-orange)](https://fair-software.eu)
![PEP8](https://badgen.net/badge/pep/8/pink?icon=python)
![Python Version](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-EUPL_v1.2-green)

Web application to see the content of IRODs, define and start processes and pipelines on a cluster.

Uses:
* flask [http://flask.pocoo.org/](http://flask.pocoo.org/)
* python-irodsclient [https://github.com/irods/python-irodsclient](https://github.com/irods/python-irodsclient)
* bootstrap library [https://getbootstrap.com/](https://getbootstrap.com/)
* conda

Start de applicatie met behulp van het script start.sh

## deployment

The application is distributed as the idms-web python-package.
Its is referenced in the env/idms_web environment file.
By creating and activating the environment the package is made available and the flask server can be started locally using:
   start.sh

When deploying on a server we use a docker-image containing the conda environment.



## Docker
### Docker-compose build
To build the docker image, use a server that has docker installed (e.g., `rivm-bioir-l02t`).
Clone the repository to this server and run the following command to build the image:
```
sudo docker-compose build
```

### Docker-compose run
To run the image, use the following command:
```
sudo docker-compose up
```

to enter the container:
```
sudo docker-compose exec idms_web bin/bash
```

#### Development configuration
By default, this uses the `docker-compose.yml` file for the configuration.
If a `docker-compose.override.yml` is present, it uses this file to override/extend the settings of the `docker-compose.yml` file.

For development, we have a standard setting override in `docker-compose.development.yml`. To use this, do the following before running:
```
ln -s docker-compose.development.yml docker-compose.override.yml
```
this creates a symlink called `docker-compose.override.yml` which links to `docker-compose.development.yml`.
Unlinking is done with `unlink docker-compose.override.yml`.

### clean images
Docker images and containers take up quite a bit of space, so you should clean up regularly. Prune the unused images with:
```
docker images prune
```
and clean up the containers with:
```
docker rm $(docker ps -aq)
```

### open ports
To view the iDMS app in the browser, you will need to use an open port to runs on.
On rivm-biofl-l01t, the ports 2048-2148 are open for testing.

If you need to turn off the firewall, you can disable puppet temporarily by setting
`noop = true` in `/etc/puppetlabs/puppet/puppet.conf`.

Perhaps you also need to disable puppet with:
```
sudo systemctl stop puppet
```
and disable the firewall fully with:
```
sudo iptables -F
```

### Page template structure

The pages in biorods use various jinja template blocks to integrate in the interface. They are described below.

block name|required|example|description
-|-|-|-
meta|no|{% block meta %}<p><meta http-equiv="refresh" content="30"\><p>{% endblock %}|will be rendered in the **head** section, and can contain meta tags, like auto refresh settings
heading|yes|{% block heading}<H2\>Resource settings</H2\>{% endblock %}|Formatted page heading, that show on top of the content page
menuname|yes|{% block menuname %}<p>menuname="jobspage"<p>{% endblock %}|links the page to its menu option. Should contain javascript menuname assignment, corresponding to **data-menuname** in base2.html menu entry
menuitems|no|{% block menuitems %}<p><li class="nav-item"\>Processes</li\><p>{% endblock %}|Used to insert submenu items in the action list
helptitle|no|{% block helptitle %} jobs {% endblock}|Page title will be used in help text viewer
helptext|no|{% block helptext}Help on this page{% endblock %}|Text going into the help text viewer
content|yes|{% block content %}List of jobs ... {% endblock %}|Actual page content goes here

#### Example page
```
{% extends 'base2.html' %}

{% block meta %}
<meta http-equiv="refresh" content="30">
{% endblock %}

{% block heading %}
<h3>
    <div class="inline">Processgroup overview</div>
    <div class="float-right header-right">
        Last refresh: <div class="refresh-time">... loading ...</div>
    </div>
</h3>
{% endblock %}

{%block menuname %}
menuname='pglist'
{% endblock %}

{% block helptitle %}
processgroups
{% endblock %}

{% block helptext %}
This page shows an overview of <emp>processgroups</emp>. Processgroups are groups of pipelines that act on a specific collection
or the output of a previous pipeline. For each project, one ore more processgroups can be configured using the processgroup tab in the
<a href="/projects">project configuration</a>
{% endblock %}

{% block content %}

{% endblock %}
```


## React JSONschema forms (rjsf)

New versions of React jsonschema forms (RJSF) cannot directly be imported in html through the script tag.
To be able to import them in flask templates, we first build a small js bundle that has the relevant functions.
This is done with npm/npx and webpack.
```
  mamba env update -f envs/rjsf_bundler.source.yaml
  conda activate rjsf_bundler
  cd rjsf
  npm install
  npx webpack
```
The resulting bundle is put in the static/js folder directly.


## Support


For questions, bug reports, or feature requests:
- Open an issue in the idms_common_irods GitHub repository.
- Reach out to the iDMS maintenance team at BIR-intern@rivm.nl


## Contributing

## License

European Union Public Licence (EUPL) v. 1.2

