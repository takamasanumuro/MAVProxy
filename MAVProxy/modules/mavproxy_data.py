#!/usr/bin/env python

import time, os
from MAVProxy.modules.lib import mp_module
from pymavlink import mavutil
import sys, traceback
import requests

from MAVProxy.modules.lib import mp_settings
import paho.mqtt.client as mqtt
import json
import numbers

class MQTTException(Exception):
    pass


class CustomModule(mp_module.MPModule):
    #Let's initiate a listener for GPS messages
    def __init__(self, mpstate):
        super(CustomModule, self).__init__(mpstate, "data", "Message listener")
        self.add_command("debug", self.cmd_debug, "Debug", ["on", "off"])

        self.debug = True
        
    
    def cmd_debug(self, args):
        if args[0] == "on":
            self.debug = True
        else:
            self.debug = False
    
    #override print function
    def print(self, msg):
        if self.debug:
            print(msg)

    def mavlink_packet(self, m):
        'handle a MAVLink packet'''
        if m.get_type() == 'GLOBAL_POSITION_INT':

            latitude = float(m.lat) / 10000000
            longitude = float(m.lon) / 10000000
        
            payload = {
                "latitude": latitude,
                "longitude": longitude
            }

            time_now = time.time()
            send_to_api(payload)
            time_after = time.time()
            print(f"Time to send to API: {time_after - time_now:.2f}s")

            time_now = time.time()
            send_to_scada(payload)
            time_after = time.time()
            print(f"Time to send to SCADA: {time_after - time_now:.2f}s")
            #print(f"LAT: {latitude:.7f} | LON: {longitude:.7f}")

        if m.get_type() == 'LOCAL_POSITION_NED':

            velocity_north = m.vx
            velocity_east = m.vyç
            total_velocity = (velocity_north**2 + velocity_east**2)**0.5

            payload = {
                "velocidade": total_velocity
            }

            send_to_scada(payload)

            #print(f"VEL-N: {velocity_north:.2f}m/s | VEL-E: {velocity_east:.2f}m/s | VEL-T: {total_velocity:.2f}m/s")

def init(mpstate):
    '''initialise module'''
    return CustomModule(mpstate)

#Function to send a dictionary to a REST API
def send_to_api(data):
    url = "http://localhost:5000/api/marker"
    payload = data
    headers = { "Content-Type": "application/json" }

    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

def send_to_scada(data):
    url = "http://44.221.0.169:8080/ScadaBR/httpds?"
    for key, value in data.items():
        url += f"{key}={value}&"
    if url[-1] == "&":
        url = url[:-1] #Remove the last "&"

    try:
        response = requests.get(url)
        print(f"Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    #id=value&id2=value2
    