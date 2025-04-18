#!/usr/bin/env python

import time, os

import requests.auth
from MAVProxy.modules.lib import mp_module
from pymavlink import mavutil
import sys, traceback
import requests

# Global variables for buffering data
data_buffer = []
BUFFER_SIZE = 20  # Adjust buffer size as needed

organization = "Innomaker"
bucket = "Innoboat"
token = "gK8YfMaAl54lo2sgZLiM3Y5CQStHip-7mBe5vbhh1no86k72B4Hqo8Tj1qAL4Em-zGRUxGwBWLkQd1MR9foZ-g=="

def time_to_send(func):
    def wrapper(*args, **kwargs):
        time_now = time.time()
        func(*args, **kwargs)
        time_after = time.time()
        print(f"Time to send to InfluxDB: {time_after - time_now:.2f}s")
    return wrapper

def make_influx_url(ip, port, organization, bucket):
    return f"http://{ip}:{port}/api/v2/write?org={organization}&bucket={bucket}&precision=ms"

def make_line_protocol(bucket, tags, data):
    line_protocol = f"{bucket},"
    for key, value in tags.items():
        line_protocol += f"{key}={value},"
    line_protocol = line_protocol[:-1]  #remove last comma
    line_protocol += " "
    for key, value in data.items():
        line_protocol += f"{key}={value},"
    line_protocol = line_protocol[:-1]  #remove last comma 

    epoch_seconds = int(time.time() * 1000)
    line_protocol += f" {epoch_seconds}"

    return line_protocol

session = requests.Session()

@time_to_send
def send_to_influxDB(line_protocol_buffer):
    if not line_protocol_buffer:
        return

    ip = "144.22.131.217"
    port = "8086"
    url = make_influx_url(ip, port, organization, bucket)

    payload = "\n".join(line_protocol_buffer)
    print(payload)

    try:
        headers = {"Authorization": f"Token {token}"}
        response = session.post(url, data=payload, headers=headers)
        #Print nothing in case of 204 (SUCCESS NO RESPONSE)
        if response.status_code != 204:
            print(f"Response: {response.text}")
    except requests.exceptions.RequestException as exception:
        print(f"Error: {exception}")

def add_to_buffer(payload):

    tags = {"source": "Pixhawk"}
    data = make_line_protocol(bucket, tags, payload)
    data_buffer.append(data)
    if len(data_buffer) >= BUFFER_SIZE:
        send_to_influxDB(data_buffer)
        # Clear the buffer after sending
        data_buffer.clear()

class CustomModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(CustomModule, self).__init__(mpstate, "data", "Message listener")
        self.add_command("debug", self.cmd_debug, "Debug", ["on", "off"])
        self.debug = True

    def cmd_debug(self, args):
        self.debug = args[0] == "on"

    def print(self, msg):
        if self.debug:
            print(msg)

    def mavlink_packet(self, m):
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

            #Make line protocol
            add_to_buffer(payload)

        '''
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

            add_to_buffer(payload)
        '''

def init(mpstate):
    '''initialise module'''
    return CustomModule(mpstate)
