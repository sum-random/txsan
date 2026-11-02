#!/usr/bin/env python3
"""activate or deactivate Sabrent drive enclosure with relay hat
attached to RPi5 GPIO, including shutting down ZFS volume in SSDs
because this manipulates ZFS volumes it must run as root"""

import subprocess
import sys
from time import sleep
import syslog
import lgpio

import config

syslog.openlog("switchnas",logoption=syslog.LOG_PID, facility=syslog.LOG_DAEMON)

if len(sys.argv) != 2:
    l=len(sys.argv)
    print(f'this script requires exactly one argument, ON or OFF {l} {sys.argv}')
    sys.exit()
if not sys.argv[1].lower() in ['on','off'] :
    print('the argument must be either ON or OFF')
    sys.exit()

gpioc = lgpio.gpiochip_open(0)

def read_sense(this_pin):
    """get value of LED sensing pin"""
    lgpio.gpio_claim_input(gpioc,this_pin)
    reading=lgpio.gpio_read(gpioc,this_pin)
    lgpio.gpio_free(gpioc,this_pin)
    return reading

def toggle_relay(the_relay):
    """simulate button press by activating relay for 1/4 second
    the 0 state is closed and the 1 state is open"""
    lgpio.gpio_claim_output(gpioc,the_relay)
    lgpio.gpio_write(gpioc,the_relay,0)
    sleep(.25)
    lgpio.gpio_write(gpioc,the_relay,1)
    lgpio.gpio_free(gpioc,the_relay)

def power_up():
    """turn main power on"""
    tries = 3
    while read_sense(config("power_led")) != 1 and tries > 0:
        tries -= 1
        toggle_relay(config("power_relay"))
        sleep(3)

def power_down():
    """turn main power off"""
    tries = 3
    while read_sense(config("power_led")) != 0 and tries > 0:
        tries -= 1
        toggle_relay(config("power_relay"))
        sleep(3)

def fan_on():
    """turn on enclosure fan"""
    tries = 3
    while read_sense(config("fan_led")) != 1 and tries > 0:
        tries -= 1
        toggle_relay(config("fan_relay"))
        sleep(3)

def fan_off():
    """turn off enclosure fan"""
    tries = 3
    while read_sense(config("fan_led")) != 0 and tries > 0:
        tries -= 1
        toggle_relay(config("fan_relay"))
        sleep(3)

def report_state():
    """write current state to syslog"""
    pl=read_sense(config("power_led"))
    fl=read_sense(config("fan_led"))
    syslog.syslog(f'power:{pl} fan:{fl}')


if sys.argv[1].lower() ==  'on':
    power_up()
    fan_on()
    report_state()
    # wait for disks to come online
    sleep(30)
else:
    fan_off()

    result = subprocess.run(['zpool', 'list', config('pool_name')],
                            capture_output=True, text=True, check=False)
    if result.returncode == 1: # not mounted
        power_down()
    else:
        result = subprocess.run(['zpool', 'export',config('pool_name')],
                                capture_output=True, text=True, check=False)
        if result.returncode == 0:
            power_down()
    report_state()

# set pushbutton relays to open before exiting
lgpio.gpio_claim_output(gpioc,config("fan_relay"),1)
lgpio.gpio_free(gpioc,config("fan_relay"))
lgpio.gpio_claim_output(gpioc,config("power_relay"),1)
lgpio.gpio_free(gpioc,config("power_relay"))
