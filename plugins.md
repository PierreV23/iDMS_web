iDMS plugins
============

Plugins allow to extend the functionality of the iDMS web application. They consist of python modules in the plugin folder.

Plugins can have integration actions executed upon load, by implementing a `setup_plugin(app)` function.

Installed plugins can be disabled by setting the module level `ENABLED` variable to `False`

Various integrations are supported:

## Extending the main menu

Menu entries can be added using the `register_item` function of the `menu_manager` object.

```python
from idms.web.app.menu_manager import menu_manager

register_item(self, item_dict, parent_name=None, before=None)
```
Dynamically appends a new menu item. If parent_name is provided, it attaches as a child item. If before is provided, will try to insert the item before the specified menu item.

The item_dict defines the menu item, and has the following entries:
Key|Value
-|-
name|item name
label|text shown in the menu
icon|icon class
url|redirect url when item is selected

## Adding datafields

Datafield and data name mappings can be registered using an instance of the DatafieldRegistry class:

### map_attribute
This will map a metadata attribtue name to a knwon datatype:
```python
def map_attribute(self, attr_name: str, datatype: str)
```

Multiple attribute mappinsg can be registerd at once using:
```python
def map_attributes(self, mapping_dict: dict):
```

### map_pattern
```python
def map_pattern(self, pattern: str, datatype: str):
```
This allows to map a regex pattern for an attribute name to a datatype


### register_type

```python
def register_type(self, name: str) -> Callable[[Type[Datafield]]
```

This decorator can be used to register new data type handlers. The handler class should inherit from the Dataield base class


### Examples


```python
from idms.web.app.utils.datafieldregistry import datafield_registry 

# Map the attribute data::importtimestamp to the type timestamp

datafield_registry.map_attribute('data::importtimestamp', 'timestamp')

# Map all attributes like sys::*::timestamp to the timestamp type

datafield_registry.map_template('sys::.*::timestamp', 'timestamp')

# Create new datafield for temperature

@datafield_registry.register_type('temperature')
def data_temperature(Datafield):
    @property
    def htmlstring(self) -> str:
        return str(f'{self.value} C')
```

### Standard data types
Type|Class|Description
-|-|-
boolean|data_boolean
bytes|data_bytes|Will use suffix (b,kB,MB,GB,TB,PB,EP)
collection_id|data_collection_id|Will find collection name by searching for ATTR_DATASETID
int|data_int
irods_collection|data_irods_collection|iRODS collection path. Links to collbrowser
irods_group|data_irods_group|User group in iRODS
irods_object|data_irods_object|Object in iRODS
irods_user|data_irods_user|User in iRODS
process|data_process|Jobengine process
processgroupguid|data_processgroupguid|Jobengine processgroup GUID
projectid|data_projectid|Jobengine project
runsheet|data_runsheet|Runsheet name
timedelta|data_timedelta|Time difference
timestamp|data_timestamp|Unix timestamp
url|data_url|URL


## Adding document viewers

The `doc_viewer_manager` from idms.web.app.components.docviewer allows for:
* Mapping extensions to document types
* Registering handlers for new document types

### Mapping extensions
```python
def register_mapping(self, objecttype, *extensions)
```
This will map all provided extensions to the specified objecttype

### Registering new document types

The `register_handler` decorator will register a new document type handler:
```python
 def register_handler(self, objecttype)
```

### Examples
```python
from idms.web.app.components.docviewer import doc_viewer_manager

# Map the .text extension to the `textfile` viewer
doc_viewer_manager.register_mapping('textfile', '.text')


# Add a python document viewer
import html

PY_VIEWER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            margin: 0;
            padding: 16px;
            background-color: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13px;
        }}
        pre {{
            margin: 0;
            white-space: pre-wrap;
            word-break: break-all;
        }}
    </style>
</head>
<body>
    <pre><code>{}</code></pre>
</body>
</html>
"""

doc_viewer_manager.register_mapping('python', '.py')

@doc_viewer_manager.register_handler('python')
def render_python(obj, path, **kwargs):
    """Render Python source code files in a simple dark-themed code viewer."""
    with obj.open('r') as fobj:
        raw_content = fobj.read()
        content = raw_content.decode('utf-8', errors='replace') if isinstance(raw_content, bytes) else raw_content

    # Escape HTML special characters (<, >, &, ") to prevent rendering issues or XSS
    safe_code = html.escape(content)
    
    rendered_html = PY_VIEWER_TEMPLATE.format(safe_code)

    return rendered_html, 200, {'Content-Type': 'text/html; charset=utf-8'}

```

## Adding action menus

Extra tabs can be added to the action pane in the top right corner, using the action_manager instance of ActionManager class:
```python
    def add_action_page(self, name, title=None, template=None, dataset=False, filterfunc=None, datafunc=None)
```

Parameter|Type|Description
-|-|-
name|str|A name for the action tab. Is not shown in the interface
title|str|Name of the action tab
template|str|Template file to render
dataset|boolean|If True, only show if a dataset is selected
filterfunc|callable|If defined, will only show if this function returns True. Is called with `filterfunc(coll_state)`
datafunc|callable|If defined, inject a data variable in the template that is the result of this function. Called with `datafunc(coll_state)`

### Examples
```python
from idms.web.app.action_manager import action_manager

# Setup a tab where you can delete a dataset
def setup_plugin(app):
    action_manager.add_action_page(self, 'delete', 'Delete', template='delete.html', dataset=True, filterunc=can_delete)

def can_delete(coll_state):
    return coll_state._meta('projectID') in current_user.projects()
```