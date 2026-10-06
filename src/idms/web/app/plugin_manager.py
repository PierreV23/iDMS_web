import importlib
import inspect
import sys
from pathlib import Path
from idms.web.app.features import FEATURES
from idms.web.app.plugin import BasePlugin

class PluginManager:
    def __init__(self, app, datafield_registry=None, menu_manager=None, doc_viewer_manager=None, action_manager=None, plugin_path="plugins"):
        self.app = app
        self.plugin_path = plugin_path
        self._data = {}
        self.datafield_registry = datafield_registry
        self.menu_manager = menu_manager
        self.doc_viewer_manager = doc_viewer_manager
        self.action_manager = action_manager
        self.loaded_plugins = {}
        self.postfork_functions = []

    def load_plugins(self):
        plugins_dir = Path(self.app.root_path) / self.plugin_path

        if not plugins_dir.exists():
            return

        base_package = plugins_dir.name

        # Ensure top-level parent package exists in sys.modules so submodules resolve properly
        if base_package not in sys.modules:
            dummy_spec = importlib.util.spec_from_loader(base_package, loader=None)
            if dummy_spec:
                parent_module = importlib.util.module_from_spec(dummy_spec)
                parent_module.__path__ = [str(plugins_dir)]
                sys.modules[base_package] = parent_module
        else:
            parent_module = sys.modules[base_package]
            if hasattr(parent_module, "__path__") and str(plugins_dir) not in parent_module.__path__:
                parent_module.__path__.append(str(plugins_dir))                

        for plugin_path in plugins_dir.iterdir():
            # Skip non-directories, hidden folders, and __pycache__
            init_file = plugin_path / '__init__.py'
            if (
                not plugin_path.is_dir()
                or plugin_path.name.startswith((".", "__"))
                or not init_file.is_file()
            ):
                continue
            
            plugin_name = plugin_path.name
            full_module_name = f"{base_package}.{plugin_name}"
            
            # Load the module dynamically from its file path
            try:
                spec = importlib.util.spec_from_file_location(full_module_name, str(init_file), submodule_search_locations=[str(plugin_path)])
                
                if spec and spec.loader:
                    plugin_module = importlib.util.module_from_spec(spec)
                    plugin_module.__package__ = full_module_name
                    sys.modules[full_module_name] = plugin_module
                    
                    spec.loader.exec_module(plugin_module)

                    # Find any class inheriting from BasePlugin inside the module
                    plugin_class = None
                    for _, obj in inspect.getmembers(plugin_module, inspect.isclass):
                        if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                            plugin_class = obj
                            break

                    if not plugin_class:
                        continue

                    # Instantiate the plugin
                    plugin_instance = plugin_class(self.app, self)

                    if not plugin_instance.enabled:
                        sys.modules.pop(full_module_name, None)
                        continue

                    # Execute setup method
                    plugin_instance.setup()

                    # Save instantiated plugin instance
                    self.loaded_plugins[plugin_name] = plugin_instance

                    if plugin_instance.optional:
                        FEATURES[plugin_name] = (plugin_instance.description, True)

                    print(f"Successfully loaded plugin: {plugin_name}")
                        
            except Exception as e:
                sys.modules.pop(full_module_name, None)
                print(f"Failed to load plugin {plugin_name}: {e}")

            
