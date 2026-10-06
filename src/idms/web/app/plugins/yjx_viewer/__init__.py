# plugins/yjx_viewer/__init__.py
import json
import xml.dom.minidom
import yaml
from flask import Blueprint, render_template
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer, XmlLexer, YamlLexer

from idms.web.app.plugin import BasePlugin

PYGMENTS_CSS = HtmlFormatter(style="monokai").get_style_defs('.highlight')

class YJXViewerPlugin(BasePlugin):
    name = "yjx_viewer"
    description = "YAML, JSON, and XML Document Viewer"
    optional = False

    def setup(self):
        # 1. Register File Mappings via PluginManager helper
        self.register_viewer_mapping('yaml', '.yaml', '.yml')
        self.register_viewer_mapping('json', '.json')
        self.register_viewer_mapping('xml', '.xml', '.xsd', '.svg')

        # 2. Register Handlers via PluginManager helper
        self.register_viewer_handler('yaml', self.render_yaml)
        self.register_viewer_handler('json', self.render_json)
        self.register_viewer_handler('xml', self.render_xml)
        
        self.bp = Blueprint(
            self.name, 
            __name__, 
            template_folder='templates'
        )
        self.app.register_blueprint(self.bp)        

    @staticmethod
    def render_yaml(obj, path, **kwargs):
        with obj.open('r') as fobj:
            raw_content = fobj.read()
            content = raw_content.decode('utf-8', errors='replace') if isinstance(raw_content, bytes) else raw_content

        parse_error = None
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as exc:
            parse_error = str(exc)

        formatter = HtmlFormatter(nowrap=False, linenos='inline', cssclass='highlight')
        code_html = highlight(content, YamlLexer(), formatter)

        rendered_page = render_template(
            'code_viewer.html',
            code_html=code_html,
            css=PYGMENTS_CSS,
            parse_error=parse_error
        )
        return rendered_page, 200, {'Content-Type': 'text/html; charset=utf-8'}

    @staticmethod
    def render_json(obj, path, **kwargs):
        with obj.open('r') as fobj:
            raw_content = fobj.read()
            content = raw_content.decode('utf-8', errors='replace') if isinstance(raw_content, bytes) else raw_content

        parse_error = None
        formatted_json = content

        try:
            parsed_data = json.loads(content)
            formatted_json = json.dumps(parsed_data, indent=2, ensure_ascii=False)
        except json.JSONDecodeError as exc:
            parse_error = f"Line {exc.lineno}, Column {exc.colno}: {exc.msg}"

        formatter = HtmlFormatter(nowrap=False, linenos='inline', cssclass='highlight')
        code_html = highlight(formatted_json, JsonLexer(), formatter)

        rendered_page = render_template(
            'code_viewer.html',
            code_html=code_html,
            css=PYGMENTS_CSS,
            parse_error=parse_error
        )
        return rendered_page, 200, {'Content-Type': 'text/html; charset=utf-8'}

    @staticmethod
    def render_xml(obj, path, **kwargs):
        with obj.open('r') as fobj:
            raw_content = fobj.read()
            content = raw_content.decode('utf-8', errors='replace') if isinstance(raw_content, bytes) else raw_content

        parse_error = None
        formatted_xml = content

        try:
            dom = xml.dom.minidom.parseString(content.encode('utf-8'))
            pretty_xml = dom.toprettyxml(indent="  ")
            formatted_xml = "\n".join([line for line in pretty_xml.splitlines() if line.strip()])
        except Exception as exc:
            parse_error = str(exc)

        formatter = HtmlFormatter(nowrap=False, linenos='inline', cssclass='highlight')
        code_html = highlight(formatted_xml, XmlLexer(), formatter)

        rendered_page = render_template(
            'code_viewer.html',
            code_html=code_html,
            css=PYGMENTS_CSS,
            parse_error=parse_error
        )
        return rendered_page, 200, {'Content-Type': 'text/html; charset=utf-8'}