from idms.web.app.plugin import BasePlugin

KNOWN_ATTRIBUTES = {
    'import_timestamp': 'timestamp'
}

KNOWN_ATTRIBUTE_TEMPLATES = {
}   

class Datafields(BasePlugin):
    name = 'datafields'
    def setup(self):
        for k, v in KNOWN_ATTRIBUTES.items():
            self.register_attribute(k, v)
