This folder /test contains files with schemata to test 6 scenarios:

1- test.json                -> valid json and valid ui file (shows placeholder in interface)
2- test_no_ui.json          -> test a file with no ui file
3- test_json_error.json     -> the json contains an error, which can not be read in python with json.loads()
4- test_react_error.json    -> the json is valid, but React can't render it
5- test_json_error_ui.json  -> the schema json is valid, the ui schema json in invalid
6- test_react_error_ui.json -> the json schemata both are valid, but React can't render the ui 

To use go to: icd <irodsZone>/system/schemata/projects, or another folder where you store the json forms 
and replace the folder of a project by the contents of test:
    irm -rf <project_name> 
    iput -r test <project_name>
    
All files will be visible then in the iDMS-web Metadata Editor for Project Metadata, and can be tested by selecting them.