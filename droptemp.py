#!/usr/bin/env python3
"""
Control fans with relay hat attached to RPi5 GPIO
Read current temperature of CPU and SSD drives
If CPU temp high, switch on blower, if CPU drops below range, switch it off
If SSD temp high, switch on enclosure fan, when SSD cools off, switch it off
"""

import syslog
import time
import re
import sys
from subprocess import Popen, PIPE
import lgpio

from config import config

syslog.openlog("droptemp",logoption=syslog.LOG_PID, facility=syslog.LOG_DAEMON)

# should pass an argument for number of minutes to run
runtime = 900 if len(sys.argv) != 2 else int(sys.argv[1]) * 60

h = lgpio.gpiochip_open(0)
fstate = 1
timenow = int(time.time())
timeend = timenow - timenow % runtime + runtime - 5
#syslog.syslog(f'now:{timenow} then:{timeend}')

def get_max_smart_temp():
    """read SSD SMART values, find temperature, return maximum value found, scaled x1000"""
    pat=re.compile(r'Temperature')
    max_temp=0
    for sdev in config('ssd_list'):
        with Popen(['smartctl','-a','/dev/'+sdev],stdout=PIPE,stderr=PIPE) as smarttext:
            stdout = smarttext.communicate()
            if smarttext.returncode == 0:
                for sline in stdout[0].decode("utf-8").split('\n'):
                    if pat.search(sline):
                        max_temp = max(max_temp,int(sline.split()[9]))
    return max_temp * 1000

def switch_sfan():
    """use relay as a pushbutton: turn on for 1/4 sec, then off again"""
    lgpio.gpio_claim_output(h, config('fan_relay'), 1)
    lgpio.gpio_write(h, config('fan_relay'), 0) #press button
    time.sleep(0.25)
    lgpio.gpio_write(h, config('fan_relay'), 1) #release button
    lgpio.gpio_free(h,config('fan_relay'))

def switch_blower_fan(new_state):
    """switch fan relay directly on or off"""
    lgpio.gpio_claim_output(h, config('blower_relay'),new_state)
    lgpio.gpio_write(h, config('blower_relay'), new_state)
    lgpio.gpio_free(h,config('blower_relay'))

def read_led(led_pin):
    """return value of selected gpio pin, wired to one of the Sabrent LEDs"""
    lgpio.gpio_claim_input(h,led_pin)
    led_value = lgpio.gpio_read(h, led_pin)
    lgpio.gpio_free(h,led_pin)
    return led_value

smart_max_last = get_max_smart_temp()
try:
    while int(time.time()) < timeend:
        pled = read_led(config('power_led'))
        fled = read_led(config('fan_led'))

        smart_max = get_max_smart_temp()

        with open(r"/sys/class/thermal/thermal_zone0/temp","r",encoding="utf-8") as File:
            current_temp = int(File.readline())

        # Turn the GPIO pin on
        # note for this relay, 0 is on and 1 is off
        if current_temp > config('setpoint')+config('band'):
            fstate = 0
            switch_blower_fan(fstate)
        if pled == 1 and fled == 0:
            if smart_max > config('setpoint')-config('band') and smart_max_last > config('setpoint')-config('band'):
                #syslog.syslog("turn enclosure fan ON")
                switch_sfan()

        # Turn the GPIO pin off
        if current_temp < config('setpoint')-config('band'):
            fstate = 1
            switch_blower_fan(fstate)
        if pled == 1 and fled == 1:
            if smart_max < config('setpoint')-config('band') and smart_max_last < config('setpoint')-config('band'):
                #syslog.syslog("turn enclosure fan OFF")
                switch_sfan()

        syslog.syslog(f'cpu:{current_temp} ssd:{smart_max} blower:{1-fstate} enclosure:{pled},{fled}')
        time.sleep(24.75)
        smart_max_last = smart_max
except KeyboardInterrupt:
    #syslog.syslog(syslog.LOG_ERR,"interrupted")
    lgpio.gpio_write(h, config('blower_relay'), 1)
lgpio.gpiochip_close(h)
