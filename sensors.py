import time
from smbus2 import SMBus
import Adafruit_DHT
import Adafruit_BMP.BMP085 as BMP085

I2C_BUS_NUM = 1
PCF8591_ADDRESS = 0x48
bus = SMBus(I2C_BUS_NUM)

def read_adc(channel=0):
    if channel < 0 or channel > 3:
        raise ValueError("ADC channel must be 0-3")
    bus.write_byte(PCF8591_ADDRESS, 0x40 + channel)
    time.sleep(0.05)
    return bus.read_byte(PCF8591_ADDRESS)

DHT_SENSOR = Adafruit_DHT.DHT11
DHT_PIN = 4
bmp = BMP085.BMP085()

def read_sensors():
    humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
    if humidity is None or temperature is None:
        humidity, temperature = -1, -1

    try:
        temp_bmp = bmp.read_temperature()
        pressure = bmp.read_pressure() / 100.0
        altitude = bmp.read_altitude()
    except Exception:
        temp_bmp, pressure, altitude = -1, -1, -1

    soil_moisture = read_adc(1)  # AIN1
    light = read_adc(0)          # AIN0

    return {
        "dht_temp": round(temperature, 1),
        "dht_humidity": round(humidity, 1),
        "bmp_temp": round(temp_bmp, 1) if temp_bmp != -1 else -1,
        "pressure": round(pressure, 2) if pressure != -1 else -1,
        "altitude": round(altitude, 2) if altitude != -1 else -1,
        "soil_moisture": soil_moisture,
        "light": light,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

if __name__ == "__main__":
    try:
        while True:
            data = read_sensors()
            print(data)
            time.sleep(2)
    except KeyboardInterrupt:
        bus.close()
        print("Stopped.")
