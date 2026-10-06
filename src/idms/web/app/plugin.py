# idms/web/app/plugins.py
from abc import ABC, abstractmethod
from flask import Flask


class BasePlugin(ABC):
    name: str = ""
    description: str = ""
    enabled: bool = True
    optional: bool = False

    def __init__(self, app: Flask, plugin_manager):
        self.app = app
        self.plugin_manager = plugin_manager

        # Track registered items owned by this specific plugin
        self.registered_menus = []
        self.registered_mappings = []
        self.registered_handlers = []
        self.registered_action_pages = []
        self.registered_datafields = {}

        if not self.name:
            self.name = self.__class__.__name__
        if not self.description:
            self.description = self.name

    @abstractmethod
    def setup(self) -> None:
        """Core plugin setup logic."""
        pass
    
    # handler for postfork operations
    def register_postfork(self, postfork_function):
        self.plugin_manager.postfork_functions.append(postfork_function)

    # --- Feature Registration Wrappers ---
    # Attribute and data types
    def register_attribute(self, attribute_name, datatype):
        if self.plugin_manager.datafield_registry:
            self.plugin_manager.datafield_registry.map_attribute(attribute_name, datatype)
        self.registered_datafields[attribute_name] = datatype

    def register_attributes(self, attributes: dict):
        if self.plugin_manager.datafield_registry:
            self.plugin_manager.datafield_registry.map_attributes(attributes)
        self.registered_datafields.update(attributes)

    def register_template(self, attribute_pattern, datatype):
        if self.plugin_manager.datafield_registry:
            self.plugin_manager.datafield_registry.map_pattern(attribute_pattern, datatype)

    def register_templates(self, attribute_pattern_dict):
        if self.plugin_manager.datafield_registry:
            self.plugin_manager.datafield_registry.map_patterns(attribute_pattern_dict)

    # Menu items
    def register_menu_item(self, name=None, url=None, icon=None, label=None, parent=None, before=None, feature=None):
        """Registers a menu item and associates it with this plugin."""
        if self.plugin_manager.menu_manager:
            menu_record = {
                'name': name or self.name,
                'url': url,
                'icon': icon,
                'label': label or self.name,
                'feature': feature or self.name
            }
            self.plugin_manager.menu_manager.register_item(menu_record, parent_name=parent, before=before)

            # Keep local reference inside the plugin instance
            self.registered_menus.append(menu_record)

    # Document viewer register
    def register_viewer_mapping(self, name: str, *extensions):
        """Registers a document viewer class and associates it with this plugin."""
        if self.plugin_manager.doc_viewer_manager:
            self.plugin_manager.doc_viewer_manager.register_mapping(name, *extensions)

            self.registered_mappings.append(
                {"plugin": self.name, "name": name, "extensions": extensions}
            )

    def register_viewer_handler(self, name: str, handler_func):
        """Register a viewer render handler with doc_viewer_manager."""
        if self.plugin_manager.doc_viewer_manager:
            self.plugin_manager.doc_viewer_manager.register_handler(name, handler_func)
            self.registered_handlers.append({"plugin": self.name, "name": name, "handler": handler_func})

    # Action pages
    def register_action_page(self, name, title=None, template=None, dataset=False, filterfunc=None, datafunc=None):                   
        if self.plugin_manager.action_manager:
            self.plugin_manager.action_manager.add_action_page(
                name,
                title,
                template=template,
                dataset=dataset,
                filterfunc=filterfunc,
                datafunc=datafunc,
                feature=self.name,
            )
            self.registered_action_pages.append({"name": name, "title": title, "template": template})
