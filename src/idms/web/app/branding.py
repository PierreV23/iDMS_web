import logging

from flask import Blueprint

logger = logging.getLogger(__name__)

def init_branding(app):
    branding_directory = app.config.get('BRANDING_DIRECTORY', app.static_folder)
    logger.info(f'Get branding from {branding_directory}')
    bp = Blueprint(
        'branding',
        __name__,
        branding_directory,
        '/branding'
    )
    app.register_blueprint(bp)
    

DEFAULT_BRANDING = {
    "APP_NAME_SHORT": "Web",     #RIVM iDMS
    "APP_NAME_LONG": "iDMS Web Portal",
    "PRIMARY_COLOR": "#2C3E50",    # Classic Slate Gray
    "SECONDARY_COLOR": "#C9C9C9",  # light grey
    "LOGO_URL": "whitelabel/whitelabel-main_icon.png",   #/static/files/beeldmerk-rijksoverheid-desktop_44.svg
    "FAVICON_URL": "whitelabel/favicons/favicon.ico",
    "FOOTER_TEXT": "Powered by Open Source Community",
    "CUSTOM_CSS": None, #"rivm_rijkshuisstyle/css/custom-rijkshuisstijl.css",
                        #"whitelabel/css/custom_styling #fonts etc.
    "CONTACT_EMAIL": "admin@organization.org"
}

def get_branding(app):
    branding = DEFAULT_BRANDING.copy()
    branding.update(app.config.get("BRANDING", {}))
    # config_branding = app.config.get("BRANDING")
    
    # for key in branding:
    #     # Check if BRANDING_APP_NAME, BRANDING_PRIMARY_COLOR, etc. exist in config
    #     if config_branding and config_branding.get(key):
    #         branding[key] = config_branding[key]
            
    return branding