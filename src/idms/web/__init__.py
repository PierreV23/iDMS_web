import sys

# The conda-forge python version has a version string like
# 3.12.12 | packaged by conda-forge | (main, Oct 22 2025, 23:25:55) [GCC 14.3.0]
# This cannot be parsed by platform.py
# Strip out the conda-forge modifier so platform.py can parse it
if "packaged by conda-forge" in sys.version:
    sys.version = sys.version.split(" | ")[0] + " " + " ".join(sys.version.split(" | ")[2:])

from idms.web.app.idms_web import create_app

create_app()