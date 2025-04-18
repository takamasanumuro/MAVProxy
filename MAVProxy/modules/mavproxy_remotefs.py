 #!/usr/bin/env python
'''Remote failsafe to detect if an external GCS is connected and if it is not, send a failsafe command to the autopilot.'''

import time, os

from MAVProxy.modules.lib import mp_module
from pymavlink import mavutil
import sys, traceback
from MAVProxy.mavproxy import MPState


class CustomModule(mp_module.MPModule):
    def __init__(self, mpstate: MPState):
        super(CustomModule, self).__init__(mpstate, "remotefs", "Remote failsafe")
        self.last_heartbeat_time = time.time()
        self.gcs_timeout = 5 # seconds without heartbeat from remote GCS
        self.failsafe_command_sent = False
        self.mpstate = mpstate


    def idle_task(self):
        self.check_active_remote_gcs()
    
    def check_active_remote_gcs(self):
        tcpin :mavutil.mavtcpin = self.mpstate.mav_outputs[0]
        if not tcpin.port and not self.failsafe_command_sent:
            print("[MAVPROXY] No remote GCS connected")
            self.send_failsafe_command()
            self.failsafe_command_sent = True
        elif tcpin.port and self.failsafe_command_sent:
            print(f"[MAVPROXY] Remote GCS connected on port {tcpin.port}")
            self.failsafe_command_sent = False

    def send_failsafe_command(self):
        self.master.mav.command_long_send(
            1, #system id
            1, #component id
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, #confirmation,
            0, #disarm,
            0, 0, 0, 0, 0, 0 #unused parameters
        )


def init(mpstate: MPState):
    '''initialise module'''
    return CustomModule(mpstate)