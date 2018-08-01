#!/bin/sh

cd /home/pi/dev
mkdir -p logs
( /usr/bin/stdbuf -oL /home/pi/dev/failsafe.py > "logs/$(date)_failsafe.log")&


( /usr/bin/stdbuf -oL /home/pi/dev/camera.sh > "logs/$(date)_camera.log" ) &
