#!/usr/bin/env python3
"""configuration helper for other tools"""

# system libraries
import json

CONFIGFILE = '/usr/local/etc/config.json'

with open(CONFIGFILE,"r",encoding='utf-8') as f:
    CONFIG = json.load(f)

def config(section=False):
    """return configuration data"""
    if section and section in CONFIG:
        return CONFIG[section]
    return CONFIG

if __name__ == '__main__':
    print(f"{CONFIG}")
