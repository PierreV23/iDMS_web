Documentation on how to edit the schemata.

In the future the rivm.json, and ui_rivm.json are generated automatically. 
For now some manual changes need to be made, to present the json form in a proper way.

## rivm.json:
- added version and renamed to version_info
- Added some explanation for users
- Removed some headers that contained confusing information
- The Bewaartermijn part was unusable, changed parts of this manually.
    - added the url to the description
    - removed old entries with * from dropdown list, they do not match with the Selectielijst

## ui_rivm.json

has the same basic structure as the rivm.json.
the ui_rivm.json is used for: 
- hiding fields 
- setting placeholders for dates to jjjj-mm-dd
    - if more than one subfields have a date they need to be wrapped in items: {}
    
## dataset_custom.json

This json schema can be used for custom key-value pairs that need to be put on a dataset

## test
The folder test contains schemata for testing error handling

put the whole folderstructure on a project in iRODS:
    ```
    cd schemata/test
    iput -r . /<rivmZone>/system/schemata/projects/<projectname>/
    ```