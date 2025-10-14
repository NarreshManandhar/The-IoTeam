from smbus2 import SMBus
import RPi.GPIO as GPIO
import time

FAN_PIN = 24
PUMP_PIN = 23

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(FAN_PIN, GPIO.OUT)
GPIO.setup(PUMP_PIN, GPIO.OUT)

I2C_BUS_NUM = 1
PCF8591_ADDRESS = 0x48
bus = SMBus(I2C_BUS_NUM)

def read_adc(channel=0):
    if channel < 0 or channel > 3:
        raise ValueError("ADC channel must be 0-3")
    bus.write_byte(PCF8591_ADDRESS, 0x40 + channel)
    time.sleep(0.05)
    return bus.read_byte(PCF8591_ADDRESS)

# Example usage:
dht_temp = 25  # Replace with actual reading
SOIL_MOISTURE_ON_THRESHOLD = 80
SOIL_MOISTURE_OFF_THRESHOLD = 120
soil_moisture_val = read_adc(1)

# Fan control
if dht_temp >= 25:
    GPIO.output(FAN_PIN, GPIO.LOW)
    fan_status = "ON"
else:
    GPIO.output(FAN_PIN, GPIO.HIGH)
    fan_status = "OFF"

# Pump control (hysteresis)
pump_status = "OFF"
if pump_status == "OFF" and soil_moisture_val < SOIL_MOISTURE_ON_THRESHOLD:
    GPIO.output(PUMP_PIN, GPIO.LOW)
    pump_status = "ON"
elif pump_status == "ON" and soil_moisture_val > SOIL_MOISTURE_OFF_THRESHOLD:
    GPIO.output(PUMP_PIN, GPIO.HIGH)
    pump_status = "OFF"
