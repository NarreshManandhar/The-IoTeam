#!/usr/bin/env python3
"""
controller.py - Plant Monitoring System
LCD priority: soil moisture, pump, fan, temperature
Full data visible on console
SQLite logging every second, AWS upload every 10 seconds
Author: The IoTeam
"""

import time
import json
import sqlite3
import socket
from pathlib import Path

from smbus2 import SMBus
import Adafruit_BMP.BMP085 as BMP085
import RPi.GPIO as GPIO
from display import update_lcd, lcd_init

# AWS libs
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

# --- Project paths and AWS details (edit if needed) ---
PROJECT_DIR = Path(__file__).resolve().parent
CERT_PATH = PROJECT_DIR / "certs" / "certificate.pem.crt"
KEY_PATH = PROJECT_DIR / "certs" / "private.pem.key"
ROOT_CA_PATH = PROJECT_DIR / "certs" / "rootCA.pem"            # or AmazonRootCA1.pem
AWS_ENDPOINT = "a1y1hr6wej3zxo-ats.iot.ap-southeast-2.amazonaws.com"
AWS_CLIENT_ID = "AUTPlantMonitor202510011906"
AWS_TOPIC = "plant/sensors/AUTPlantMonitor202510011906"

# --- GPIO setup ---
DHT11_PIN = 17
SOIL_MOISTURE_PIN = 18
FAN_PIN = 24
PUMP_PIN = 23

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(DHT11_PIN, GPIO.OUT)
GPIO.setup(SOIL_MOISTURE_PIN, GPIO.IN)
GPIO.setup(FAN_PIN, GPIO.OUT)
GPIO.setup(PUMP_PIN, GPIO.OUT)

# --- I2C ADC setup ---
I2C_BUS_NUM = 1
PCF8591_ADDRESS = 0x48
bus = SMBus(I2C_BUS_NUM)

def read_adc(channel=0):
    if channel < 0 or channel > 3:
        raise ValueError("ADC channel must be 0-3")
    bus.write_byte(PCF8591_ADDRESS, 0x40 + channel)
    time.sleep(0.05)
    # read twice sometimes more reliable
    return bus.read_byte(PCF8591_ADDRESS)

# --- BMP085 setup ---
bmp_sensor = BMP085.BMP085(busnum=I2C_BUS_NUM)

# --- DHT11 reading (primary) ---
MAX_UNCHANGE_COUNT = 100
STATE_INIT_PULL_DOWN = 1
STATE_INIT_PULL_UP = 2
STATE_DATA_FIRST_PULL_DOWN = 3
STATE_DATA_PULL_UP = 4
STATE_DATA_PULL_DOWN = 5

def read_dht11_dat():
    GPIO.setup(DHT11_PIN, GPIO.OUT)
    GPIO.output(DHT11_PIN, GPIO.HIGH)
    time.sleep(0.05)
    GPIO.output(DHT11_PIN, GPIO.LOW)
    time.sleep(0.02)
    GPIO.setup(DHT11_PIN, GPIO.IN, GPIO.PUD_UP)

    unchanged_count = 0
    last = -1
    data = []

    while True:
        current = GPIO.input(DHT11_PIN)
        data.append(current)
        if last != current:
            unchanged_count = 0
            last = current
        else:
            unchanged_count += 1
            if unchanged_count > MAX_UNCHANGE_COUNT:
                break

    state = STATE_INIT_PULL_DOWN
    lengths = []
    current_length = 0

    for current in data:
        current_length += 1
        if state == STATE_INIT_PULL_DOWN:
            if current == GPIO.LOW:
                state = STATE_INIT_PULL_UP
        elif state == STATE_INIT_PULL_UP:
            if current == GPIO.HIGH:
                state = STATE_DATA_FIRST_PULL_DOWN
        elif state == STATE_DATA_FIRST_PULL_DOWN:
            if current == GPIO.LOW:
                state = STATE_DATA_PULL_UP
        elif state == STATE_DATA_PULL_UP:
            if current == GPIO.HIGH:
                current_length = 0
                state = STATE_DATA_PULL_DOWN
        elif state == STATE_DATA_PULL_DOWN:
            if current == GPIO.LOW:
                lengths.append(current_length)
                state = STATE_DATA_PULL_UP

    if len(lengths) != 40:
        return False

    shortest_pull_up = min(lengths)
    longest_pull_up = max(lengths)
    halfway = (longest_pull_up + shortest_pull_up) / 2
    bits = []
    the_bytes = []
    byte = 0

    for length in lengths:
        bit = 1 if length > halfway else 0
        bits.append(bit)

    for i in range(len(bits)):
        byte = (byte << 1) | bits[i]
        if (i + 1) % 8 == 0:
            the_bytes.append(byte)
            byte = 0

    checksum = (the_bytes[0] + the_bytes[1] + the_bytes[2] + the_bytes[3]) & 0xFF
    if the_bytes[4] != checksum:
        return False

    # returns humidity, temperature (as original)
    return the_bytes[0], the_bytes[2]

# --- Soil moisture ---
def read_soil_moisture():
    return GPIO.input(SOIL_MOISTURE_PIN)  # 1=Dry, 0=Wet

# --- SQLite setup ---
DB_PATH = PROJECT_DIR / "plant_data.db"
conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    dht_temp REAL,
    dht_humidity REAL,
    bmp_temp REAL,
    bmp_pressure REAL,
    bmp_altitude REAL,
    photoresistor INTEGER,
    soil_moisture INTEGER,
    fan_status TEXT,
    pump_status TEXT,
    aws_status TEXT
)
""")
conn.commit()

# --- AWS helper functions ---
def dns_lookup_ok(hostname: str) -> bool:
    try:
        socket.gethostbyname(hostname)
        return True
    except Exception:
        return False

def connect_aws():
    """
    Attempt to establish an MQTT over TLS connection to AWS IoT Core.
    Returns mqtt_connection or None on failure.
    """
    # quick DNS check
    if not dns_lookup_ok(AWS_ENDPOINT):
        print(f"[AWS] DNS lookup failed for endpoint {AWS_ENDPOINT}", flush=True)
        return None

    try:
        event_loop_group = io.EventLoopGroup(1)
        host_resolver = io.DefaultHostResolver(event_loop_group)
        client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

        mqtt_connection = mqtt_connection_builder.mtls_from_path(
            endpoint=AWS_ENDPOINT,
            cert_filepath=str(CERT_PATH),
            pri_key_filepath=str(KEY_PATH),
            ca_filepath=str(ROOT_CA_PATH),
            client_bootstrap=client_bootstrap,
            client_id=AWS_CLIENT_ID,
            clean_session=False,
            keep_alive_secs=30
        )

        print("[AWS] Connecting to AWS IoT Core...", flush=True)
        connect_future = mqtt_connection.connect()
        connect_future.result()  # wait for connection
        print("[AWS] Connected to AWS IoT Core", flush=True)
        return mqtt_connection

    except Exception as e:
        print(f"[AWS] Connect failed: {e}", flush=True)
        return None

def log_to_aws(mqtt_connection, data: dict):
    """
    Publish a JSON payload to the configured topic using an existing mqtt_connection.
    Raises exception on publish failure.
    """
    if mqtt_connection is None:
        raise RuntimeError("No MQTT connection available")

    payload_json = json.dumps(data)
    mqtt_connection.publish(
        topic=AWS_TOPIC,
        payload=payload_json,
        qos=mqtt.QoS.AT_LEAST_ONCE
    )
    print(f"[AWS] Published to {AWS_TOPIC}: {payload_json}", flush=True)

# --- Main loop ---
def main():
    lcd_init()
    update_lcd("The IoTeam", "Plant Monitoring")
    time.sleep(2)
    update_lcd("System Starting", "")
    time.sleep(1)

    print("Plant Monitoring System Started", flush=True)
    print("="*160, flush=True)
    print("{:<6} {:<6} {:<6} {:<4} {:<4} {:<4} {:<4} {:<6} {:<6} {:<6} {:<6} {:<6}".format(
        "Time","T","H","S","P","F","A","D","BMP_T","BMP_P","Photo","AWS"
    ), flush=True)
    print("-"*160, flush=True)

    counter = 0
    aws_counter = 0
    aws_status = "0"
    db_status = "0"

    # Try to connect at startup
    mqtt_connection = connect_aws()

    # track reconnect attempts every N seconds (try every 30s)
    reconnect_attempt_timer = 0
    RECONNECT_INTERVAL = 30

    try:
        while True:
            # read sensors
            photoresistor_val = read_adc(0)
            bmp_temp = bmp_sensor.read_temperature()
            try:
                bmp_pressure = bmp_sensor.read_pressure() / 100.0
            except Exception:
                # in rare cases BMP library might fail momentarily
                bmp_pressure = -1.0
            try:
                bmp_altitude = bmp_sensor.read_altitude()
            except Exception:
                bmp_altitude = -1.0

            dht_result = read_dht11_dat()
            soil_state = read_soil_moisture()

            if dht_result:
                dht_humidity, dht_temp = dht_result
            else:
                dht_humidity, dht_temp = -1, int(bmp_temp)

            # fan control (active LOW assumed)
            if dht_temp is not None and dht_temp >= 25:
                GPIO.output(FAN_PIN, GPIO.LOW)
                fan_status = 1
            else:
                GPIO.output(FAN_PIN, GPIO.HIGH)
                fan_status = 0

            # pump control (active LOW assumed)
            if soil_state == 1:  # dry
                GPIO.output(PUMP_PIN, GPIO.LOW)
                pump_status = 1
            else:
                GPIO.output(PUMP_PIN, GPIO.HIGH)
                pump_status = 0

            # AWS publish every 10s (non-blocking publish; errors handled)
            aws_counter += 1
            if aws_counter >= 10:
                aws_counter = 0
                payload = {
                    "dht_temp": dht_temp,
                    "dht_humidity": dht_humidity,
                    "soil_moisture": soil_state,
                    "fan_status": fan_status,
                    "pump_status": pump_status,
                    "bmp_temp": bmp_temp,
                    "bmp_pressure": bmp_pressure,
                    "bmp_altitude": bmp_altitude,
                    "photoresistor": photoresistor_val,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                if mqtt_connection is None:
                    # try to reconnect if possible
                    reconnect_attempt_timer += 1
                    if reconnect_attempt_timer >= RECONNECT_INTERVAL:
                        print("[AWS] Attempting reconnect...", flush=True)
                        mqtt_connection = connect_aws()
                        reconnect_attempt_timer = 0
                    aws_status = "0"
                else:
                    try:
                        log_to_aws(mqtt_connection, payload)
                        aws_status = "1"
                    except Exception as e:
                        print(f"[AWS] Publish failed: {e}", flush=True)
                        aws_status = "E"
                        # set mqtt_connection to None so we attempt reconnect later
                        try:
                            mqtt_connection.disconnect().result()
                        except Exception:
                            pass
                        mqtt_connection = None
            else:
                aws_status = "0"

            # SQLite logging (always try, replace missing values with safe defaults)
            safe_dht_temp = float(dht_temp) if isinstance(dht_temp, (int, float)) else -1.0
            safe_dht_humidity = float(dht_humidity) if isinstance(dht_humidity, (int, float)) else -1.0
            safe_bmp_temp = float(bmp_temp) if isinstance(bmp_temp, (int, float)) else -1.0
            safe_bmp_pressure = float(bmp_pressure) if isinstance(bmp_pressure, (int, float)) else -1.0
            safe_bmp_alt = float(bmp_altitude) if isinstance(bmp_altitude, (int, float)) else -1.0

            try:
                cursor.execute("""
                    INSERT INTO sensor_data (
                        timestamp, dht_temp, dht_humidity, bmp_temp, bmp_pressure, bmp_altitude,
                        photoresistor, soil_moisture, fan_status, pump_status, aws_status
                    )
                    VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    safe_dht_temp, safe_dht_humidity, safe_bmp_temp, safe_bmp_pressure, safe_bmp_alt,
                    int(photoresistor_val), int(soil_state), str(fan_status), str(pump_status), aws_status
                ))
                conn.commit()
                db_status = "1"
            except Exception as e:
                db_status = "E"
                print("DB Insert Error:", e, flush=True)

            # update LCD with short format required
            soil_str = "D" if soil_state == 1 else "W"
            line1 = f"S={soil_str} P={pump_status} A={aws_status} D={db_status}"
            line2 = f"T={int(dht_temp)} H={dht_humidity if dht_humidity!=-1 else '--'} F={fan_status}"
            update_lcd(line1[:16], line2[:16])

            # Print for console/laptop (clear per-line output)
            print("{:<6} {:<6} {:<6} {:<4} {:<4} {:<4} {:<4} {:<6} {:<6} {:<6} {:<6} {:<6}".format(
                counter,
                int(dht_temp) if isinstance(dht_temp, (int,float)) else "--",
                dht_humidity if dht_humidity != -1 else "--",
                soil_str,
                pump_status,
                fan_status,
                aws_status,
                db_status,
                int(bmp_temp) if isinstance(bmp_temp, (int,float)) else "--",
                int(bmp_pressure) if isinstance(bmp_pressure, (int,float)) else "--",
                photoresistor_val,
                aws_status
            ), flush=True)

            time.sleep(1)
            counter += 1

    except KeyboardInterrupt:
        print("\nExiting program...", flush=True)
    finally:
        try:
            if mqtt_connection:
                mqtt_connection.disconnect().result()
        except Exception:
            pass
        GPIO.cleanup()
        bus.close()
        conn.close()

if __name__ == "__main__":
    main()
