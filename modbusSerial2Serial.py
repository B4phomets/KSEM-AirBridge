"""
Modbus RTU Bridge - Fix: Frame Separation
Verhindert das Zusammenkleben von Nachrichten durch erzwungene Pausen.
"""

import serial
import time
import sys

# --- CONFIGURATION ---
PORT_INVERTER = "/dev/ttyACM0"
PORT_SOURCE   = "/dev/ttySC1"
BAUDRATE      = 38400

SERIAL_PARAMS = {
    "baudrate": BAUDRATE,
    "parity": serial.PARITY_NONE,
    "stopbits": serial.STOPBITS_TWO,
    "bytesize": serial.EIGHTBITS,
    "timeout": 0.2
}

# 3.5 Zeichenzeiten bei 38400 Baud sind ca. 1ms. 
# Wir nutzen 4ms zur absoluten Sicherheit.
MODBUS_SILENT_INTERVAL = 0.004 

def hex_log(data):
    return " ".join(f"{b:02X}" for b in data)

def run_bridge():
    try:
        inv = serial.Serial(PORT_INVERTER, **SERIAL_PARAMS)
        src = serial.Serial(PORT_SOURCE, **SERIAL_PARAMS)
        # Buffer leeren
        inv.reset_input_buffer()
        src.reset_input_buffer()
        print(f"[*] Bridge aktiv: {PORT_INVERTER} <-> {PORT_SOURCE} (8N2)")
    except Exception as e:
        print(f"[!] Fehler: {e}")
        return

    while True:
        if inv.in_waiting > 0:
            # 1. Anfrage vom Inverter lesen
            time.sleep(0.01) # Kurz warten, um das ganze Paket zu erfassen
            req = inv.read(inv.in_waiting)
            
            if req:
                print(f"\n[INV ->] {hex_log(req)}")
                
                # 2. Weiterleiten an Quelle (vorher Buffer leeren)
                src.reset_input_buffer()
                src.write(req)
                src.flush()
                
                # 3. Auf Antwort warten
                resp = b""
                start_time = time.time()
                while (time.time() - start_time) < 0.3: # 300ms Fenster
                    if src.in_waiting > 0:
                        time.sleep(0.01) # Zeit geben damit Paket vollständig ankommt
                        resp = src.read(src.in_waiting)
                        break
                
                if resp:
                    print(f"[-> SRC] Antwort: {hex_log(resp)}")
                    
                    # --- FIX: Paket-Trennung ---
                    # Wir warten das Silent Interval, bevor wir senden
                    time.sleep(MODBUS_SILENT_INTERVAL)
                    
                    inv.write(resp)
                    inv.flush()
                    
                    # Erzwungene Pause nach dem Senden, damit der Bus zur Ruhe kommt
                    time.sleep(MODBUS_SILENT_INTERVAL)
                else:
                    print("[!] Timeout von Quelle")

        time.sleep(0.005)

if __name__ == "__main__":
    run_bridge()
