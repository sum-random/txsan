#!/usr/bin/bash

ULE="/usr/local/etc"
. $ULE/config.sh

exec 2>>/var/log/vpnssh.err.log
printf "%s %d\n" "$(date)" $$ >>/var/log/vpnssh.err.log

# if gw not reachable try rebooting
if ! ping -qt 20 -Ac 15 $(awk '/via/ {print $3}' <(ip route get 1.1.1.1)) ; then
  if [ $((RANDOM % 10)) -eq 0 ] ; then
    echo GW unreachable at $(date), rebooting
    #reboot
  fi
fi | logger -t vpnsshlink

SSHPORT=$((RANDOM % 10000 + 20000))

HOMEBASE=$(awk '/^Address/ && !/127.0.0/ {print $2}' <(nslookup $VPNHOST))
[ "xx" = "${HOMEBASE}xx" ] && HOMEBASE="${VPNHOST}"

kill -9 $(ps wwaux | grep ssh | grep vpn-tx2 | awk '{print $2}')

echo ":$HOMEBASE:" | logger -t vpnsshlink

ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=15 -R *:$SSHPORT:localhost:22 -L 2222:${IOIP}:22 -C -i ${HC}/.ssh/id_rsa ${USR}@$HOMEBASE "sudo route delete ${VPNIP}; sleep 5; sudo ppp -direct vpn-tx2;sleep 300"

