from abc import ABC, abstractmethod
from typing import Type, Dict, Optional, Callable, Any
import re
import json
import importlib

class Datafield(ABC):
    """Abstract base for all datafield wrappers."""
    
    def __init__(self, name: str, value: Any, datatype: Optional[str] = None):
        self.name = name
        self.value = value
        self.datatype = datatype or getattr(self, "default_datatype", "base")

    @property
    def htmlstring(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return str(self.value)

class DatafieldRegistry:
    """Central registry for datafield types, attribute maps, and patterns."""

    def __init__(self):
        self._types: Dict[str, Type[Datafield]] = {}
        self._known_attributes: Dict[str, str] = {}
        self._templates: Dict[re.Pattern, str] = {}
        
    def load_known_attributes(self, filename):
        if filename.endswith('.json'):
            with open(filename, 'r') as f:
                data = json.load(f)
                self._known_attributes = data.get('known_attributes', {})
                self._templates = data.get('templates', {})
        elif filename.endswith('.py'):
            spec = importlib.util.spec_from_file_location('datafield_cfg', filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.map_attributes(getattr(module, 'known_attributes', {}))
            self.map_patterns(getattr(module, 'templates', {}))

    def register_type(self, name: str) -> Callable[[Type[Datafield]], Type[Datafield]]:
        """Decorator to register a Datafield class."""
        def decorator(cls: Type[Datafield]) -> Type[Datafield]:
            self._types[name] = cls
            return cls
        return decorator

    def map_attribute(self, attr_name: str, datatype: str):
        """Explicitly map an attribute name to a data type."""
        self._known_attributes[attr_name] = datatype

    def map_attributes(self, mapping_dict: dict):
        """Explicitly map an attribute name to a data type."""
        self._known_attributes.update(mapping_dict)

    def map_pattern(self, pattern: str, datatype: str):
        """Map a regex pattern to a data type."""
        self._templates[re.compile(pattern)] = datatype
        
    def map_patterns(self, patterns: dict):
        """Map dict of attribute tempates and types"""
        for pattern, datatype in patterns.items():
            self.map_pattern(pattern, datatype)

    def resolve_type(self, attr: str, unit: Optional[str] = None) -> str:
        if unit and unit in self._types:
            return unit
        if attr in self._known_attributes:
            return self._known_attributes[attr]
        for pattern, dtype in self._templates.items():
            if pattern.match(attr):
                return dtype
        return None

    def create(self, name: str, value: Any, unit: Optional[str] = None) -> Datafield:
        dtype = self.resolve_type(name, unit)
        if dtype is None:
            return self._types["base"](name=name, value=value, datatype=unit)
        cls = self._types.get(dtype, self._types["base"])
        try:
            return cls(name=name, value=value, datatype=dtype)
        except Exception:
            # Fallback to base type if construction fails
            return self._types["base"](name=name, value=value, datatype=dtype)
    
    @property
    def known_attributes(self):
        return self._known_attributes

# Singleton registry instance
datafield_registry = DatafieldRegistry()