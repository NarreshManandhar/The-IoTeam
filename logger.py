import sqlite3
import time
import json
from awscrt import mqtt
from awsiot import mqtt_connection_builder

def init_db():
    conn = sqlite3.connect("plant_data.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        temperature REAL,
        humidity REAL,
        pressure REAL,
        altitude REAL,
        soil_moisture INTEGER,
        light INTEGER,
        pump TEXT,
        fan TEXT
    )''')
    conn.commit()
    conn.close()

def log_to_db(data):
    conn = sqlite3.connect("plant_data.db")
    c = conn.cursor()
    c.execute("INSERT INTO sensor_data (timestamp,temperature,humidity,pressure,altitude,soil_moisture,light,pump,fan) VALUES (?,?,?,?,?,?,?,?,?)",
        (time.strftime("%Y-%m-%d %H:%M:%S"), data["temperature"], data["humidity"], data["pressure"], data["altitude"], data["soil_moisture"], data["light"], data["pump"], data["fan"]))
    conn.commit()
    conn.close()

def connect_aws():
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint="a1y1hr6wej3zxo-ats.iot.ap-southeast-2.amazonaws.com",
        cert_filepath="certs/certificate.pem.crt",
        pri_key_filepath="certs/private.pem.key",
        ca_filepath="certs/rootCA.pem",
        client_id="AUTPlantMonitor202510011906",
        clean_session=False,
        keep_alive_secs=30
    )
    mqtt_connection.connect().result()
    print("✅ Connected to AWS IoT Core")
    return mqtt_connection

def log_to_aws(mqtt_connection, data):
    topic = "plant/sensors/AUTPlantMonitor202510011906"
    mqtt_connection.publish(
        topic=topic,
        payload=json.dumps(data),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )
    print(f"Published to AWS topic {topic}: {json.dumps(data)}")
