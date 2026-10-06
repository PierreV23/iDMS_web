#!/bin/bash

# This script is meant to be used to turn on all features for current iDMS users
# so they have the same user experience when moving to user-configureable web app features


for home in $(iquest "%s" "SELECT COLL_NAME WHERE META_COLL_ATTR_NAME = 'ngsweb::path'")
do
    echo "Check $home"
    # Try determining if the script has already run for this home
    imeta ls -C $home ngsweb::feature::projects | grep value > /dev/null
    if [ $? -ne 0 ]
    then
        echo "Modifying $home"
        ichmod -M delete_metadata rods $home
        for feature in actions jobs minilims projects provenance reference treeview
        do
            imeta set -C $home ngsweb::feature::$feature '"true"'
        done
        ichmod -M null rods $home
    fi
done

