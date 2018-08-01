#!/bin/sh

cd /home/pi/dev

( /home/pi/dev/failsafe.py > failsafe.log)&


( /home/pi/dev/camera.sh > camera.log ) &
