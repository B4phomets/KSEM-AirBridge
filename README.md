# Wireless KSEM Inverter Connection

A Modbus RTU to TCP Gateway to connect the **Kostal Smart Energy Meter (KSEM) G2** over ethernet to the Kostal Plenticore G2 Inverter. 

## Features
- **Dual-Block Sync:** Fetches 148 registers (100 + 48) via TCP.
- **Decoupled Timing:** Independent network polling and serial serving.
- **Industrial Config:** Pre-set for 38400 Baud, 8N2 on `/dev/ttySC0`.

## Installation
```bash
sudo apt update
sudo apt install python3-pymodbus python3-serial
git clone https://github.com
cd Wireless-KSEM-Inverter-Connection
python3 modbus_gateway.py
```


## Known Issues
- The script needs the pymodbus lib V3.8.6, which you'll get with Raspbian Trixie.

  You can check the version with

```bash
  sudo apt show python3-pymodbus
```
