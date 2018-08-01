#!/bin/bash

#don't activate until comms are established
while true; do
  ping 10.0.0.2 -W1 -c 1 2>/dev/null 1>/dev/null && break
done

echo "Connection with client established. Failsafe activated."


