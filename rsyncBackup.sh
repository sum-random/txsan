#!/usr/bin/bash

#define vars
STARTHR=$(date '+%H')
SNAPDATE=$(date '+%Y%m%d')
ULE="/usr/local/etc"
. ${ULE}/config.sh

# function to restart PPP service
connecttovpn() {
  pkill -9 -x rsync
  pkill -9 -x pppd
  sleep 10
  pppd call texas
  sleep 10
}

# stop here if previous process is still running
if [ $(pgrep -x rsync | wc -l) -gt 0 ] ; then
  echo already running
  exit # quit if already running
fi | logger -t startup

# check if PPP connection is valid
TRIES=5
while ! ping -qt 10 -Ac 3 $JVPN && [ $((TRIES--)) -gt 0 ]; do 
  connecttovpn
done | logger -t VPN

# check if pool is online, turn it on if not
if ! zpool list -H | grep -q ${SR} ; then
  if ! zpool import 2>&1 | grep -q ${SR} ; then 
    ${RB}/switchnas.py on
  fi
  for NASDRIVE in $DRIVES; do
    if ! [ -b /dev/${NASDRIVE} ] ; then
      echo "Drive ${NASDRIVE} not found, exiting"
      exit
    fi
  done
  zpool import 2>&1 | grep -q ${SR} && zpool import ${SR} && sleep 5
fi | logger -t NAS

# final check then copy files and take snapshot
if [ -d $STAU ] ; then
  OPTS="--stop-at="
  if [ $(date '+%H') -ge 5 ] ; then
    OPTS="${OPTS}23:45 --bwlimit=100k" #throttle during people hours
  else
    OPTS="${OPTS}05:45" #run full speed from midnight to 6am
  fi
  rsync -av --delete $OPTS -e "ssh -Ci ${HC}/.ssh/id_rsa -p 2222 -l ${USR}" $IOSHR $IODEST &
  rsync -av --delete $OPTS --filter=". ${ULE}/backupfilter.txt" $JSHR $JDEST&
  wait
  zfs list -t snapshot | grep -q ${SNAPDATE} || zfs snapshot -r ${SR}@${SNAPDATE}
  # remove daily snapshots more than two weeks old, leaving monday as weeklies
  [ $(date '+%u') -ne 1 ] && echo zfs destroy -r ${SR}@$(date -d '14 days ago' '+%Y%m%d')
  # remove weeklies from previous month, leaving first weekly behind
  LM=$(date -d '2 months ago' '+%Y%m')
  [ $(date '+%u') -eq 1 ] && [ $(date '+%d') -gt 7 ] && zfs list -t snapshot | grep -e "${LM}[1-3]|${LM}0[89]" | while read SNAP; do echo zfs destroy -r ${SNAP}; done
  # remove monthlies older than 3 months and leave quarterlies behind
  LQ=$(date -d '6 months ago' '+%Y%m')
  date '+%m' | grep -qE '03 06 09 12' || zfs list -t snapshot | grep ${LQ} | while read SNAP; do echo zfs destroy -r ${SNAP}; done
fi 2>&1 | logger -t rsync 

# if the copy operation was short, turn off the pool array, leave it running if the rsync took longer than an hour
if [ $(date '+%H') -eq ${STARTHR} ] ; then # if under an hour power off the HDs until next run
    zfs wait ${SR}
    zpool export ${SR}
    sleep 30 #wait to let I/O finish 
    ${RB}/switchnas.py off
fi | logger -t NAS
