import Adafruit_DHT
import Adafruit_BMP.BMP085 as BMP085
import RPi.GPIO as GPIO
import time

# --- GPIO Setup ---
SOIL_PIN = 17   # Soil moisture digital pin
LDR_PIN = 27    # Photoresistor pin (digital, comparator output)

GPIO.setmode(GPIO.BCM)
GPIO.setup(SOIL_PIN, GPIO.IN)
GPIO.setup(LDR_PIN, GPIO.IN)

# --- Sensor Setup ---
DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 4  # GPIO where DHT11 data pin is connected

bmp = BMP085.BMP085()  # For BMP180/085 sensor

def read_sensors():
    """Reads data from all sensors and returns a dictionary"""

    # --- DHT11: Temp & Humidity ---
    humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
    if humidity is None or temperature is None:
        humidity, temperature = -1, -1  # error values

    # --- BMP180: Pressure, Temp, Altitude ---
    try:
        temp_bmp = bmp.read_temperature()
        pressure = bmp.read_pressure() / 100.0  # Pa → hPa
        altitude = bmp.read_altitude()
    except Exception:
        temp_bmp, pressure, altitude = -1, -1, -1

    # --- Soil Moisture ---
    soil_state = GPIO.input(SOIL_PIN)
    soil_moisture = "Wet" if soil_state == 0 else "Dry"

    # --- Light Sensor ---
    light_state = GPIO.input(LDR_PIN)
    light = "Bright" if light_state == 0 else "Dark"

    return {
        "dht_temp": round(temperature, 1),
        "dht_humidity": round(humidity, 1),
        "bmp_temp": round(temp_bmp, 1) if temp_bmp != -1 else -1,
        "pressure": round(pressure, 2) if pressure != -1 else -1,
        "altitude": round(altitude, 2) if altitude != -1 else -1,
        "soil": soil_moisture,
        "light": light,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

if __name__ == "__main__":
    # Quick test
    try:
        while True:
            data = read_sensors()
            print(data)
            time.sleep(2)
    except KeyboardInterrupt:
        GPIO.cleanup()
        print("Stopped.")
