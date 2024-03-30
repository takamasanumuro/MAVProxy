 #!/usr/bin/env python
'''Instrumentation'''

import time, os

from MAVProxy.modules.lib import mp_module
from pymavlink import mavutil
import sys, traceback

class CustomModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(CustomModule, self).__init__(mpstate, "instrumentation", "Custom instrumentation values")
        self.add_command("ss", self.cmd_sendtest, "Send a test message")
        '''initialisation code'''

    def cmd_sendtest(self, args):
        #self.master.mav.instrumentation_send(10, 20, 30, 40, 50)
        #Generate random values for the above command
        import random
        tensao_bateria = random.uniform(23, 25.5)
        corrente_bateria = random.uniform(60, 70)
        corrente_bombordo = random.uniform(50, 60)
        corrente_estibordo = random.uniform(70, 80)
        corrente_painel = random.uniform(0, 6)
        print("[MAVPROXY] Enviando valores de teste")
        self.master.mav.instrumentation_send(tensao_bateria, corrente_bateria, corrente_bombordo, corrente_estibordo, corrente_painel)

    def mavlink_packet(self, m):
        'handle a MAVLink packet'''
        if m.get_type() == 'INSTRUMENTATION':
            print(f"[MAVPROXY-RESPOSTA]Tensão: {m.tensao_bateria:.2f}V | Corrente: {m.corrente_bateria:.2f}A")
        

def init(mpstate):
    '''initialise module'''
    return CustomModule(mpstate)