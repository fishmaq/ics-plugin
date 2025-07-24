rofi_output=$(cat events.txt | rofi -dmenu -p calendar)
if [[ "$rofi_output" == "reload" || "$rofi_output" == " " ]];then
  python3 test.py
  ./ics-plugin.sh
fi
