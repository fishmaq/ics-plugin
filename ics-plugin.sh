#!/bin/bash
rofi_output=$(cat $ICS_PLUGIN_EVENTS_LOCATION | rofi -dmenu -p calendar)
if [[ "$rofi_output" == "reload" || "$rofi_output" == " " ]];then
  python3 /home/itsv.org.sv-services.at/martin.cerny@itsv.at/.ics-plugin/sync.py
  $HOME/.ics-plugin/ics-plugin.sh
fi
