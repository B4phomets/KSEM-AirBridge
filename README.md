markdown

# Wireless KSEM Inverter Connection (KSEM-AirBridge)

A robust Modbus TCP-to-RTU Gateway designed to connect the **Kostal Smart Energy Meter (KSEM) G2** over Ethernet to a **Kostal Plenticore G2** Inverter via RS485.

## Features
- **Hybrid Data Sync:** Efficiently fetches 148+ registers using active polling and passive TCP listening.
- **Decoupled Timing:** Independent execution of network polling and serial serving to ensure minimal latency.
- **Industrial Standards:** Pre-configured for 38400 Baud, 8N2 (standard for Kostal RTU communication).
- **Thread-Safe:** Shared memory architecture for reliable data handling between interfaces.

---

## Installation

### 1. Requirements
Ensure your Raspberry Pi has a **static IP** address configured in your router.

### 2.1 Download Repository and Dependencies
```bash
sudo apt update
sudo apt install python3-pymodbus python3-serial
git clone https://github.com
cd KSEM-AirBridge
```

### 2.2 Verify Pymodbus Version
This script requires Pymodbus v3.8.6 (shipped with Raspberry Pi OS "Trixie" or newer).

```bash
  sudo apt show python3-pymodbus
```

### 3. Configuration

#### 3.1 KSEM Web Interface Settings
To ensure time-critical data reaches the gateway immediately, configure the KSEM as a Modbus TCP Master:

 - Log into the KSEM Web Dashboard.
 - Open the menu and navigate to Modbus Settings.
 - Under Modbus TCP Master, add the Raspberry Pi's Static IP and Port (e.g., 192.168.178.150, Port 5020).

#### 3.2 Script Parametrization
Edit modbus_gateway.py to match your environment:

 - TCP Server Settings: Set the IP and Port to match the "Master" settings you entered in the KSEM dashboard, i.e. the RPi's IP and port
 - TCP Polling Settings: Set the TCP_POLLING_IP to your KSEM's IP address.
 - RTU Settings: Configure the SERIAL_PORT according to your RS485 adapter (e.g., /dev/ttyACM0 or /dev/ttySC0).

## Deployment

### Manual Start
To test the connection, run the script directly:

```bash
python3 modbus_gateway.py
```

## Run as a System Service
To ensure the gateway starts automatically on boot, use the provided service file:

1. Adjust the paths in ksem-gateway.service (use absolute paths, e.g., /home/pi/...):
```bash
[Service]
ExecStart=/usr/bin/python3 /home/EVCC_Admin/KSEM-AirBridge/modbusGateway.py
WorkingDirectory=/home/EVCC_Admin/KSEM-AirBridge/
...
User=EVCC_Admin
```

2. Install the service:
```bash
sudo cp ./ksem-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ksem-gateway.service
sudo systemctl start ksem-gateway.service

```


## Known Issues
- Library Version: The script is designed for pymodbus v3.8.6, which is shipped with Raspbian Trixie. You can check the version of pymodbus with

```bash
  sudo apt show python3-pymodbus
```
