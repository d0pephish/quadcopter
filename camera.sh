#!/bin/sh
raspivid -n -fl -w 640 -h 480 -b 5000000 -fps 15 -t 0 -o - | gst-launch-1.0 -v fdsrc ! h264parse ! rtph264pay config-interval=1 pt=96 ! udpsink host=10.0.0.2  port=5600 &
