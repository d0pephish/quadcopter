#!/bin/sh

( /home/pi/dev/failsafe.sh > failsafe.log)&


( /home/pi/dev/camera.sh > camera.log ) &
