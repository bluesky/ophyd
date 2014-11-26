#!/bin/bash
# Open the IPython configuration for the ophyd profile
# Usage: edit_ipy_conf.sh [profile_name]
#        (profile_name defaults to 'ophyd')

PROFILE="${1:-ophyd}"
CONFIG_FILE=`ipython locate profile $PROFILE`/ipython_config.py

echo "Profile is:                  $PROFILE"
echo "Configuration file location: $CONFIG_FILE"

if [ -n "$EDITOR" ];
then
    $EDITOR $CONFIG_FILE
else
    editor $CONFIG_FILE
fi
