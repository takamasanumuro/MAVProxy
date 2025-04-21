#!/usr/bin/env python

import enum
import time, os

import requests.auth
from MAVProxy.modules.lib import mp_module
from pymavlink import mavutil
import sys, traceback
import requests
import random

class BatterySimulator:
    """
    A simple battery voltage simulator.
    
    Parameters
    ----------
    capacity_ah : float
        Battery capacity in amp‑hours (Ah).
    voltage_full : float
        Voltage when fully charged (V).
    voltage_empty : float
        Voltage when fully discharged (V) or when discharging below this causes battery damage or loss of life
    internal_resistance : float
        Internal resistance (ohms) causing voltage drop under load.
    initial_soc : float, optional
        Initial state of charge (0.0–1.0). Default is 1.0.
    noise_std : float, optional
        Standard deviation of Gaussian noise to add to voltage (V). Default is 0.
    """

    class BatteryState(enum.Enum):
        STANDBY = 0,
        DISCHARGING = 1,
        CHARGING = 2
        
    def __init__(self,
                capacity_ah: float,
                voltage_full: float,
                voltage_empty: float,                
                internal_resistance: float,
                initial_soc: float = 1.0,
                noise_std:float = 0.0):

        self.voltage_full = voltage_full
        self.voltage_empty = voltage_empty
        self.capacity_ah = capacity_ah * 3600
        self.internal_resistance = internal_resistance
        self.soc = max(0,0, min(1.0, initial_soc))
        self.noise_std = noise_std
        self._voltage = self._compute_voltage(0.0) #at zero load
        self.state = self.BatteryState.DISCHARGING

    def _compute_voltage(self, load_current:float) -> float:
        open_circuit_voltage = self.voltage_empty + (self.voltage_full - self.voltage_empty) * self.soc
        voltage_drop = load_current * self.internal_resistance
        voltage = open_circuit_voltage - voltage_drop
        if self.noise_std > 0:
            voltage += random.gauss(0.0, self.noise_std)
        return max(0.0, voltage)
    
    def step(self, load_current: float, dt: float):
        if (self.soc <= 0.005 and self.state == self.BatteryState.DISCHARGING):
            self.state = self.BatteryState.CHARGING
            print("Battery is empty, switching to charging mode.")
        elif (self.soc >= 0.995 and self.state == self.BatteryState.CHARGING):
            self.state = self.BatteryState.DISCHARGING
            print("Battery is full, switching to discharging mode.")
        if (self.state == self.BatteryState.CHARGING):
            load_current = -load_current

        drained = load_current * dt
        new_charge = self.soc * self.capacity_ah - drained
        self.soc = max(0.0, new_charge / self.capacity_ah)
        self._voltage = self._compute_voltage(load_current)

    @property
    def voltage(self) -> float:
        '''Get the latest simulated terminal voltage(V)'''
        return self._voltage
    
    @property
    def state_of_charge(self) -> float:
        '''Get the current state of charge(0.0-1.0)'''
        return self.soc

    def reset(self, soc: float = 1.0):
        '''Resets the simulator to a given SOC'''
        self.soc(max(0.0, min(1.0, soc)))
        self._voltage = self._compute_voltage(0.0)


battery_sim = BatterySimulator(capacity_ah = 5.0,
                               voltage_full= 54.6,
                               voltage_empty= 48.0, 
                               internal_resistance = 0.1,
                               initial_soc = 1.0,
                               noise_std = 0.0)
# Global variables for buffering data
data_buffer = []
BUFFER_SIZE = 20  # Adjust buffer size as needed

organization = "Innomaker"
bucket = "Innoboat" #database
measurement = "Innoboat" #table name
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
    line_protocol = f"{measurement},"
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
            #battery_sim.step(5.0, 5)
            #battery_voltage = battery_sim.voltage
            #tensao_bombordo = battery_voltage - 0.3
            #tensao_boreste = battery_voltage - 0.4
        
            payload = {
                "latitude": latitude,
                "longitude": longitude,
                "velocidade_norte": velocity_north_m_s,
                "velocidade_leste": velocity_east_m_s,
                "velocidade": velocity,
                "heading": heading
                #"tensao-barramento": battery_voltage,
                #"[BB]Voltage": tensao_bombordo,
                #"[BE]Voltage": tensao_boreste
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
