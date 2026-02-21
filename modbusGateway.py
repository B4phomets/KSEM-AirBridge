"""
Wireless KSEM Inverter Connection
A Modbus TCP to RTU Gateway for Kostal KSEM G2.

Copyright (c) 2024 YourName/YourUser

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import threading
import time
import sys

# --- IMPORT HANDLING (Compatibility for python3-pymodbus from APT) ---

# Newer Pymodbus versions (3.x)
from pymodbus.client import ModbusTcpClient
from pymodbus.server import (StartSerialServer,StartTcpServer)
from pymodbus import (FramerType,ModbusException,pymodbus_apply_logging_config)

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# Debugging threads requre debugpy lib
try:
    import debugpy
    debugpy.debug_this_thread()
    #pymodbus_apply_logging_config("DEBUG")
except:
    print("[main] debugpy lib not imported") 

# If desired you can add optional output for debugging
DEBUG_MSG = False

# =================================================================
# --- CONFIGURATION ---
# =================================================================

# TCP Polling Settings (Polling data from the KSEM)
TCP_POLLING_IP       = "192.168.178.100"
TCP_POLLING_PORT     = 502
TCP_POLLING_TIMEOUT  = 5.0
TCP_POLLING_INTERVAL = 1       # Global delay after one full cycle

# TCP Server (for receiving data from the KSEM master)
TCP_LISTENING_IP     = "192.168.178.150"
TCP_LISTENING_PORT   = 5020

# RTU Settings (Serving data via RS485)
SERIAL_PORT     = "/dev/ttyACM0"
BAUDRATE        = 38400
PARITY          = 'N'
STOPBITS        = 2
BYTESIZE        = 8
RTU_SLAVE_ID    = 1

# Polling registers

# --- KONFIGURATION FÜR KOSTAL KSEM REGISTERBEREICHE ---
# Format: (Modbus_Start_Adresse, Anzahl_Register, Ziel_Offset_im_Speicher)
# Der Ziel_Offset enthält deinen gewünschten +1 Shift für den Inverter-Zugriff.

POLLING_TASKS = [
    # --- GRUPPE 1: Momentanwerte (Summen- & Phasenwerte) ---
    # Bereich: 0 bis 147 (Gesamt: 148)
    #(0, 100, 1),                 # Teil A: Indizes 0-99 -> Speicher 1
    #(100, 48, 101),              # Teil B: Indizes 100-147 -> Speicher 101

    # --- GRUPPE 2: Interne Energiewerte (Zählerstände) ---
    # Bereich: 512 bis 791 (Gesamt: 280)
    (512, 100, 513),             # Teil A: Indizes 512-611 -> Speicher 513
    (612, 100, 613),             # Teil B: Indizes 612-711 -> Speicher 613
    (712, 80, 713),              # Teil C: Indizes 712-791 -> Speicher 713

    # --- GRUPPE 3: KSEM / RM PnP Management ---
    # Größe laut Angabe: 57 Register (8192 bis 8248)
    (8192, 57, 8193),            # Komplett in einem Block möglich
]

# =================================================================


def debug_message(msg: str):
    if DEBUG_MSG:
        print(msg)


class SharedDataBlock(ModbusSequentialDataBlock):
    def __init__(self, address, values):
        # Initialisiert die Basisklasse mit Startadresse 0 und n Null-Werten
        super().__init__(address, values)
        self.data_lock = threading.Lock()

    @classmethod
    def create(cls):
        super().create()

    def getValues(self, address, count=1):

        # The StartSerialServer() fucntion increases the adress by one for data access. As the server just provides data we decrease the address for th

        """Sicheres Lesen der Werte aus dem Basisspeicher"""
        with self.data_lock:
            # Nutzt die Logik der Basisklasse (inkl. Fehlerprüfung)
            values = super().getValues(address, count)
            
        # Einfacher Print der Anfrage und der Antwort
        debug_message(f"--> [RTU ANFRAGE] Inverter liest Adr: {address-1}, Anzahl: {count}")
        debug_message(f"<-- [RTU ANTWORT] Daten gesendet: {values}")
        
        return values

    def setValues(self, address, values):
        """Sicheres Schreiben der Werte in den Basisspeicher"""
        with self.data_lock:
            # Nutzt die Logik der Basisklasse für das eigentliche Update
            super().setValues(address, values)
        # Einfacher Print der Anfrage und der Antwort
        debug_message(f"--> [TCP INPUT] Inverter writes Adr: {address-1}, Data: {values}")

def tcp_poll_worker(data_block: SharedDataBlock):
    """Priorisierter Background Thread für effizientes Abfragen"""
    client = ModbusTcpClient(TCP_POLLING_IP, port=TCP_POLLING_PORT, timeout=TCP_POLLING_TIMEOUT)
    
    debug_message(f"[TCP] Priorisiertes Polling gestartet: {TCP_POLLING_IP}")
    
    while True:
        try:
            if not client.connected:
                if not client.connect():
                    time.sleep(5)
                    continue
            
            for start, count, offset in POLLING_TASKS:
                res = client.read_holding_registers(address=start, count=count, slave=1)
                if res and not res.isError():
                    data_block.setValues(offset, res.registers)
                time.sleep(0.01) # Kurze Pause zur Netzwerkschonung

        except Exception as e:
            print(f"[TCP] Fehler im priorisierten Worker: {e}")
            
        time.sleep(TCP_POLLING_INTERVAL)


def run_tcp_server(data_block: SharedDataBlock):
    """Thread: Acts as a Modbus TCP Server to receive pushed data"""

    store   = ModbusSlaveContext(hr=data_block)
    #context = ModbusServerContext(slaves=store, single=True)
    context = ModbusServerContext(slaves={RTU_SLAVE_ID: store, 255: store}, single=False)

    # TCP_IP_LISTENING
    print(f"[TCP Server] Listening for pushes on {TCP_LISTENING_IP}:{TCP_LISTENING_PORT}...")
    StartTcpServer(context=context, address=(TCP_LISTENING_IP, TCP_LISTENING_PORT))


def run_rtu_server(data_block: SharedDataBlock):
    """Main Thread: Serves RTU requests via RS485 interface"""
    # Initialize data block with start address 0
    store = ModbusSlaveContext(hr=data_block)
    context = ModbusServerContext(slaves={RTU_SLAVE_ID: store}, single=False)
    
    print(f"[RTU Server] Active on {SERIAL_PORT} (38400, 8N2)")

    try:
        StartSerialServer(
            context=context,
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            framer="rtu",
            stopbits=STOPBITS,
            bytesize=BYTESIZE,
            parity=PARITY
        )
    except Exception as e:
        print(f"[RTU] Critical error on {SERIAL_PORT}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Initialisiere den Speicher für den kompletten 16-Bit Adressraum
    # (0x0000 bis 0xFFFF = 65536 Register)
    shared_block = SharedDataBlock(0, [0] * 65536)

    # 1. Thread: Polling (Pi fragt KSEM aktiv ab)
    t_poll = threading.Thread(target=tcp_poll_worker, args=(shared_block,), daemon=True)
    t_poll.start()

    # 2. Thread: TCP Server (KSEM/andere Master pushen Daten zum Pi)
    # Da StartTcpServer blockiert, muss er in einen eigenen Thread
    t_tcp_srv = threading.Thread(target=run_tcp_server, args=(shared_block,), daemon=True)
    t_tcp_srv.start()

    # 3. Main Thread: RTU Server (Wechselrichter fragt Pi via RS485 ab)
    # StartSerialServer blockiert und hält das Skript am Laufen
    try:
        run_rtu_server(shared_block)
    except KeyboardInterrupt:
        print("[main] Skript durch Benutzer beendet.")
        sys.exit(0)
