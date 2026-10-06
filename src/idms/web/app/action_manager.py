import os
import json

class ActionManager:
    def __init__(self, json_filepath=None):
        self._actionpanes = {}
        if json_filepath:
            self.load_from_json(json_filepath)
            
    def load_from_json(self, json_filepath):
        """Loads or reloads action tabs from a JSON configuration file."""
        if os.path.exists(json_filepath):
            with open(json_filepath, "r", encoding="utf-8") as f:
                self._actionpanes = json.load(f)
                
    def items(self):
        return self._actionpanes
    
    def current_items(self, coll_state):
        def is_active(item_config):
            filter_func = item_config.get('filterfunc')
            return filter_func is None or filter_func(coll_state)

        return {k: v for k, v in self._actionpanes.items() if is_active(v)}
    
    # TODO: Add filter function that allows showing or hiding action pages
    # based on context    
    def add_action_page(self, name, title=None, template=None, dataset=False, filterfunc=None, datafunc=None, feature=None):
        self._actionpanes[name] = {
            'title': title or name,
            'template': template,
            'dataset': dataset,
            'filterfunc': filterfunc,
            'datafunc': datafunc,
            'feature': feature
        }
        
action_manager = ActionManager()