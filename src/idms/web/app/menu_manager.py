import json
import os
from copy import deepcopy
from flask import url_for
from flask_login import current_user

class MenuManager:
    def __init__(self, json_filepath=None):
        self._items = []
        if json_filepath:
            self.load_from_json(json_filepath)

    def load_from_json(self, json_filepath):
        """Loads or reloads menu items from a JSON configuration file."""
        if os.path.exists(json_filepath):
            with open(json_filepath, "r", encoding="utf-8") as f:
                self._items = json.load(f)

    def register_item(self, item_dict, parent_name=None, before=None):
        """
        Dynamically appends a new menu item.
        If parent_name is provided, it attaches as a child item.
        """
        if not parent_name:
            target_list = self._items
        else:
            parent = self._find_item_by_name(self._items, parent_name)
            if parent:
                if "children" not in parent:
                    parent["children"] = []            
                target_list = parent["children"]
            else:
                return False
            
        if before:
            for item, index in enumerate(target_list):
                if item.get('name') == before:
                    target_list.insert(index, item_dict)
                    return True
        
        target_list.append(item_dict)
        return True

    def extend_items(self, items_list):
        """Extends the root menu with a list of menu items."""
        self._items.extend(items_list)

    def _find_item_by_name(self, items, name):
        """Helper to find an item by name recursively."""
        for item in items:
            if item.get("name") == name:
                return item
            if "children" in item:
                found = self._find_item_by_name(item["children"], name)
                if found:
                    return found
        return None

    def _can_access(self, item):
        """Evaluates feature toggles and admin permissions against current_user."""
        if item.get("feature") and not getattr(current_user, "feature", lambda f: True)(item["feature"]):
            return False
        if item.get("require_admin") and not getattr(current_user, "is_admin", False):
            return False
        return True

    def _resolve_url(self, item):
        """Resolves Flask endpoint or raw URL string."""
        if "endpoint" in item:
            args = item.get("args", {})
            return url_for(item["endpoint"], **args)
        return item.get("url", "#")

    def get_visible_menu(self):
        """
        Generates the context-aware, filtered menu structure
        for the currently authenticated user.
        """
        if not current_user.is_authenticated:
            return []

        # Use deepcopy to prevent mutating internal base config state
        menu_copy = deepcopy(self._items)
        filtered_menu = []

        for item in menu_copy:
            if not self._can_access(item):
                continue

            item["href"] = self._resolve_url(item)

            if "children" in item:
                valid_children = []
                for child in item["children"]:
                    if self._can_access(child):
                        child["href"] = self._resolve_url(child)
                        valid_children.append(child)
                item["children"] = valid_children

            filtered_menu.append(item)

        return filtered_menu
    
menu_manager = MenuManager()    