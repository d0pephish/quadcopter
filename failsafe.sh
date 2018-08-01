#!/bin/bash

#don't activate until comms are established
while true; do
  ping 10.0.0.2 -W1 -c 1 2>/dev/null 1>/dev/null && break
done

echo "Connection with client established. Failsafe activated."

while true; do
  test -e /tmp/disable_failsafe && break
  ping 10.0.0.2 -c 1 -W5 2>/dev/null 1>/dev/null && ( echo good heartbeat at $(date) ) || ( reboot -f || init 0 )
  sleep 2
done
