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

# --- IMPORT HANDLING ---

# Newer Pymodbus versions (3.x)
from pymodbus.client import ModbusTcpClient
from pymodbus.server import (StartSerialServer,StartTcpServer)
from pymodbus import (FramerType,ModbusException,pymodbus_apply_logging_config)
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# Debugging threads requre debugpy lib
try:
    import debugpy
    debugpy.debug_this_thread()
    pymodbus_apply_logging_config("DEBUG")
except:
    print("[main] debugpy lib not imported") 

# Toggle extended console output for debugging
DEBUG_MSG = False

# =================================================================
# --- CONFIGURATION ---
# =================================================================

# TCP Server Settings (Receiving pushed data from the KSEM master)
TCP_LISTENING_IP     = "192.168.178.150"
TCP_LISTENING_PORT   = 5020

# TCP Polling Settings (Polling data from the KSEM)
TCP_POLLING_IP       = "192.168.178.100"
TCP_POLLING_PORT     = 502
TCP_POLLING_TIMEOUT  = 5.0
TCP_POLLING_INTERVAL = 1

# RTU Settings (Serving data to the Inverter via RS485)
SERIAL_PORT     = "/dev/ttyACM0"
BAUDRATE        = 38400
PARITY          = 'N'
STOPBITS        = 2
BYTESIZE        = 8
RTU_SLAVE_ID    = 1


# --- KOSTAL KSEM REGISTER RANGE CONFIGURATION ---
# Format: (Modbus_Start_Address, Register_Count, Target_Memory_Offset)
# The target offset includes a +1 shift to accommodate specific Inverter access requirements.

POLLING_TASKS = [
    # --- GROUP 1: Instantaneous Values (Totals & Phase Values) ---
    # Range: 0 to 147 (Total: 148)
    # (0, 100, 1),                # Part A: Indices 0-99 -> Memory 1
    # (100, 48, 101),             # Part B: Indices 100-147 -> Memory 101

    # --- GROUP 2: Internal Energy Values (Counters) ---
    # Range: 512 to 791 (Total: 280)
    (512, 100, 513),             # Part A: Indices 512-611 -> Memory 513
    (612, 100, 613),             # Part B: Indices 612-711 -> Memory 613
    (712, 80, 713),              # Part C: Indices 712-791 -> Memory 713

    # --- GROUP 3: KSEM / RM PnP Management ---
    # Size: 57 Registers (8192 to 8248)
    (8192, 57, 8193),            # Processed as a single block
]

# =================================================================


def debug_message(msg: str):
    if DEBUG_MSG:
        print(msg)


class SharedDataBlock(ModbusSequentialDataBlock):
    def __init__(self, address, values):
        # Thread-safe data block for sharing registers between TCP and RTU interfaces
        super().__init__(address, values)
        self.data_lock = threading.Lock()

    @classmethod
    def create(cls):
        super().create()

    def getValues(self, address, count=1):
        # Safe read access for the RTU server with offset logging
        with self.data_lock:
            # Use base class logic for data retrieval and error checking
            values = super().getValues(address, count)
            
        # Logging the RTU request (Note: StartSerialServer might shift address internally)
        debug_message(f"--> [RTU ANFRAGE] Inverter liest Adr: {address-1}, Anzahl: {count}")
        debug_message(f"<-- [RTU ANTWORT] Daten gesendet: {values}")
        
        return values

    def setValues(self, address, values):
        # Safe write access for the TCP polling worker/server
        with self.data_lock:
            # Update the underlying data store
            super().setValues(address, values)

        debug_message(f"--> [TCP INPUT] Inverter writes Adr: {address-1}, Data: {values}")

def tcp_poll_worker(data_block: SharedDataBlock):
    # High-priority background thread for active Modbus TCP polling
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

        except Exception as e:
            print(f"[TCP] Error in priority worker: {e}")
            
        time.sleep(TCP_POLLING_INTERVAL)


def run_tcp_server(data_block: SharedDataBlock):
    # Secondary interface: Acts as a TCP Server to receive pushed data from masters
    store   = ModbusSlaveContext(hr=data_block)
    # Support both specific RTU ID and Broadcast/Standard IDs
    context = ModbusServerContext(slaves={RTU_SLAVE_ID: store, 255: store}, single=False)

    print(f"[TCP Server] Listening for pushes on {TCP_LISTENING_IP}:{TCP_LISTENING_PORT}...")
    StartTcpServer(context=context, address=(TCP_LISTENING_IP, TCP_LISTENING_PORT))


def run_rtu_server(data_block: SharedDataBlock):
    # Main interface: Serves RTU requests to the Inverter via RS485
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
    # Initialize memory for the full 16-bit address space (0x0000 to 0xFFFF)
    shared_block = SharedDataBlock(0, [0] * 65536)

    # 1. Start Polling Thread (Active polling of KSEM)
    t_poll = threading.Thread(target=tcp_poll_worker, args=(shared_block,), daemon=True)
    t_poll.start()

    # 2. Start TCP Server Thread (Passive reception of data)
    # StartTcpServer is blocking, so it requires its own thread
    t_tcp_srv = threading.Thread(target=run_tcp_server, args=(shared_block,), daemon=True)
    t_tcp_srv.start()

    # 3. Start RTU Server (Main Thread)
    # This call is blocking and keeps the script alive to serve Inverter requests
    try:
        run_rtu_server(shared_block)
    except KeyboardInterrupt:
        print("[main] Script terminated by user.")
        sys.exit(0)
