from idms.web.app.plugin import BasePlugin

TOOLING_TEMPLATES = {
    'sys::consistency::.*::timestamp': 'timestamp',
}     

class Datafields(BasePlugin):
    name = 'irods_tools'
    def setup(self):
        self.register_templates(TOOLING_TEMPLATES)        