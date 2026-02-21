markdown

# Wireless KSEM Inverter Connection (KSEM-AirBridge)

A robust Modbus TCP-to-RTU Gateway designed to connect the **Kostal Smart Energy Meter (KSEM) G2** over Ethernet to a **Kostal Plenticore G2** Inverter via RS485.

For deeper insights into the architectural design and performance decisions (TCP Push vs. Polling), please refer to the **Technical Architecture & Experimental Insights** section at the end.

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

## Technical Architecture & Design Decisions

**Strategic Data Handling: TCP Push vs. Polling**

The Kostal KSEM G2 provides a wide array of Modbus registers, which this gateway categorizes into **time-critical** and **non-time-critical** data to ensure optimal system performance:

 - **Time-Critical Registers (TCP Push):** Instantaneous values such as power, current, and voltage are vital for the inverter's real-time control loops (e.g., zero-point regulation or battery management).
   - **The 200ms Factor:** The KSEM completes a measuring cycle approximately every **200 ms**. While this interval is the pulse of the power management system, it is significantly longer than typical local area network (LAN) delays, which usually operate in the sub-millisecond range.
   - **Maximizing Efficiency:** By utilizing the KSEM Data Push for these registers, the gateway eliminates unnecessary "polling lag." The KSEM actively transmits data the moment a measuring cycle is completed. This ensures the inverter receives the most recent measurement immediately, synchronized with the KSEM's internal clock, without waiting for the next polling trigger.
 - **Non-Time-Critical Registers (Background Polling):** Static information (serial numbers, software versions, SunSpec identification) and slow-changing cumulative energy counters (total kWh) do not require high-speed updates.
   - **Optimizing Throughput:** These registers are handled via a dedicated **Background Polling Worker**. This separation prevents the high-priority "Push" channel from being congested with static data, ensuring that critical regulation packets always have the highest possible throughput and priority.


### Performance Advantage over Transparent Piping

A simple "piping" approach—transparently forwarding RTU requests directly from the Inverter to a TCP target—often leads to severe synchronization issues.

**Experimental Insights**:
During development and testing with a Raspberry Pi (using a USB-RS485 interface connected via a Modbus RTU-to-TCP bridge), several critical issues were identified:

 - **Request/Response Misalignment:** There is often an unpredictable delay in network-based serial bridges. In some scenarios, the Inverter requests registers more frequently than the bridge can process and return the answers.
 - **Packet Concatenation:** Due to these delays, multiple responses occasionally get concatenated into a single TCP packet. This prevents the Inverter from correctly parsing the individual Modbus frames.
 - **Desynchronization:** In the worst-case scenario, a response is delayed so significantly that it is delivered as an answer to a subsequent request. This results in the Inverter receiving completely wrong data for the requested registers, which can lead to dangerous or unstable regulation behavior in power management.

By strategically splitting the data flow into High-Speed Push (for regulation) and Background Polling (for metadata), this gateway provides a rock-solid, decoupled buffer. It ensures that the Inverter's RTU requests are always answered immediately with the most recent data available in memory, completely eliminating the risks of network-induced desynchronization or misaligned responses.

