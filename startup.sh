#!/bin/sh


( /usr/bin/stdbuf -oL /home/pi/dev/camera.sh > "/home/pi/dev/logs/$(date | sed -e 's/ /_/g')_camera.log" ) & 

( cd /home/pi/dev/ && /usr/bin/stdbuf -oL /home/pi/dev/failsafe.py > "/home/pi/dev/logs/$(date | sed -e 's/ /_/g' )_failsafe.log") 
