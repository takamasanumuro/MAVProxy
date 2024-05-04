#!/usr/bin/env python

import time, os

import requests.auth
from MAVProxy.modules.lib import mp_module
from pymavlink import mavutil
import sys, traceback
import requests

from MAVProxy.modules.lib import mp_settings



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
            velocity_north_m_s = float(m.vx / 100)
            velocity_east_m_s = float(m.vy / 100)
            velocity = (velocity_north_m_s ** 2 + velocity_east_m_s ** 2) ** 0.5
            heading = float(m.hdg / 100)
        
            payload = {
                "latitude": latitude,
                "longitude": longitude,
                "velocidade_norte": velocity_north_m_s,
                "velocidade_leste": velocity_east_m_s,
                "velocidade": velocity,
                "heading": heading
            }

            send_to_influxDB(payload)

        if m.get_type() == 'ATTITUDE':
            roll = float(m.roll)
            pitch = float(m.pitch)
            yaw = float(m.yaw)
            rollspeed = float(m.rollspeed)
            pitchspeed = float(m.pitchspeed)
            yawspeed = float(m.yawspeed)

            payload = {
                "roll": roll,
                "pitch": pitch,
                "yaw": yaw,
                "rollspeed": rollspeed,
                "pitchspeed": pitchspeed,
                "yawspeed": yawspeed
            }

            send_to_influxDB(payload)


def init(mpstate):
    '''initialise module'''
    return CustomModule(mpstate)

def time_to_send(func):
    def wrapper(*args, **kwargs):
        time_now = time.time()
        func(*args, **kwargs)
        time_after = time.time()
        print(f"Time to send to InfluxDB: {time_after - time_now:.2f}s")
    return wrapper

def make_influx_url(ip, port, organization, bucket):
    return f"http://{ip}:{port}/api/v2/write?org={organization}&bucket={bucket}&precision=s"

def make_line_protocol(bucket, tags, data):
    line_protocol = f"{bucket},"
    for key, value in tags.items():
        line_protocol += f"{key}={value},"
    line_protocol = line_protocol[:-1]  #remove last comma
    line_protocol += " "
    for key, value in data.items():
        line_protocol += f"{key}={value},"
    line_protocol = line_protocol[:-1]  #remove last comma 

    epoch_seconds = int(time.time())
    line_protocol += f" {epoch_seconds}"

    return line_protocol


@time_to_send
def send_to_influxDB(data):
    organization = "Innomaker"
    bucket = "Innoboat"
    token = "gK8YfMaAl54lo2sgZLiM3Y5CQStHip-7mBe5vbhh1no86k72B4Hqo8Tj1qAL4Em-zGRUxGwBWLkQd1MR9foZ-g=="

    ip = "44.221.0.169"
    port = "8086"

    url = make_influx_url(ip, port, organization, bucket)

    tags = {
        "source": "Pixhawk"
    }

    line_protocol = make_line_protocol(bucket, tags, data)

    try:

        headers = {
             "Authorization": f"Token {token}"
        }

        response = requests.post(url, data=line_protocol, headers=headers)
        #Print nothing in case of 204 ( SUCCESS NO RESPONSE)
        if response.status_code != 204:
            print(f"Response: {response.text}")
    except requests.exceptions.RequestException as exception:
        print(f"Error: {exception}")


    