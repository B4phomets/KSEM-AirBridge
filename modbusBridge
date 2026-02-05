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
try:
    # Newer Pymodbus versions (3.x)
    from pymodbus.client import ModbusTcpClient
    from pymodbus.server import StartSerialServer
except ImportError:
    # Older Pymodbus versions (2.x)
    from pymodbus.client.sync import ModbusTcpClient
    from pymodbus.server.sync import StartSerialServer

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# =================================================================
# --- CONFIGURATION ---
# =================================================================

# TCP Settings (Polling data from the KSEM)
TCP_TARGET_IP   = "192.168.178.100"
TCP_PORT        = 502
TIMEOUT_TCP     = 5.0
POLL_INTERVAL   = 0.1       # Global delay after one full cycle

# RTU Settings (Serving data via RS485)
SERIAL_PORT     = "/dev/ttySC0"
BAUDRATE        = 38400
PARITY          = 'N'
STOPBITS        = 2
BYTESIZE        = 8
RTU_SLAVE_ID    = 1

# Block Settings
BLOCK_1_SIZE         = 100  # First request: 100 registers
BLOCK_2_SIZE         = 48   # Second request: 48 registers
TOTAL_REGISTER_COUNT = BLOCK_1_SIZE + BLOCK_2_SIZE

# =================================================================

# Global shared memory in RAM
shared_memory = [0] * TOTAL_REGISTER_COUNT

def tcp_refresh_worker():
    """Background Thread: Fetches data in two blocks (100 & 48) via TCP"""
    global shared_memory
    client = ModbusTcpClient(TCP_TARGET_IP, port=TCP_PORT, timeout=TIMEOUT_TCP)
    
    print(f"[TCP] Polling started: {TOTAL_REGISTER_COUNT} registers total from {TCP_TARGET_IP}")
    
    while True:
        try:
            if not client.connected:
                client.connect()
            
            # --- BLOCK 1 (Registers 0 to 99) ---
            try:
                res1 = client.read_holding_registers(address=0, count=BLOCK_1_SIZE, slave=1)
            except TypeError:
                res1 = client.read_holding_registers(address=0, count=BLOCK_1_SIZE, unit=1)

            if res1 and not res1.isError():
                shared_memory[0:BLOCK_1_SIZE] = res1.registers
            else:
                print(f"[TCP] Error in Block 1 (Addr 0-{BLOCK_1_SIZE-1})")

            # Small delay between TCP requests to prevent network congestion
            time.sleep(0.01)

            # --- BLOCK 2 (Registers 100 to 147) ---
            try:
                # Start address follows the first block
                res2 = client.read_holding_registers(address=BLOCK_1_SIZE, count=BLOCK_2_SIZE, slave=1)
            except TypeError:
                res2 = client.read_holding_registers(address=BLOCK_1_SIZE, count=BLOCK_2_SIZE, unit=1)

            if res2 and not res2.isError():
                # Write 48 values starting at index 100
                shared_memory[BLOCK_1_SIZE : TOTAL_REGISTER_COUNT] = res2.registers
            else:
                print(f"[TCP] Error in Block 2 (Addr {BLOCK_1_SIZE}-{TOTAL_REGISTER_COUNT-1})")
                
        except Exception as e:
            print(f"[TCP] Communication error: {e}")
            
        time.sleep(POLL_INTERVAL)

class SharedDataBlock(ModbusSequentialDataBlock):
    """Custom data block to serve values directly from the shared_memory array"""
    def getValues(self, address, count=1):
        start = address
        end = address + count
        if end > TOTAL_REGISTER_COUNT:
            # Return zeros if master requests more than available
            return [0] * count
        return shared_memory[start:end]

def run_rtu_server():
    """Main Thread: Serves RTU requests via RS485 interface"""
    # Initialize data block with start address 0
    block = SharedDataBlock(0, [0] * TOTAL_REGISTER_COUNT)
    store = ModbusSlaveContext(hr=block)
    context = ModbusServerContext(slaves={RTU_SLAVE_ID: store}, single=False)
    
    print(f"[RTU] Server active on {SERIAL_PORT} (38400, 8N2)")
    print(f"[RTU] Registered total size: {TOTAL_REGISTER_COUNT} Holding Registers")
    
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
    # 1. Start TCP polling thread
    t = threading.Thread(target=tcp_refresh_worker, daemon=True)
    t.start()
    
    # 2. Start RTU Server in the main thread
    run_rtu_server()
