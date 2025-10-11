FAN_PIN = 24
PUMP_PIN = 23

GPIO.setup(FAN_PIN, GPIO.OUT)
GPIO.setup(PUMP_PIN, GPIO.OUT)

# Fan control based on temperature
if dht_result:
    _, dht_temp = dht_result
    if dht_temp >= 25:
        GPIO.output(FAN_PIN, GPIO.LOW)   # LOW = relay ON → fan ON
        fan_status = "ON"
    else:
        GPIO.output(FAN_PIN, GPIO.HIGH)  # HIGH = relay OFF → fan OFF
        fan_status = "OFF"
else:
    fan_status = "Unknown"

# Pump control based on soil moisture
soil_state = read_soil_moisture()  # 1 = dry, 0 = wet
if soil_state == 1:  # dry
    GPIO.output(PUMP_PIN, GPIO.LOW)   # LOW = relay ON → pump ON
    pump_status = "ON"
else:
    GPIO.output(PUMP_PIN, GPIO.HIGH)  # HIGH = relay OFF → pump OFF
    pump_status = "OFF"
