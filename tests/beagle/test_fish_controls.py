# import Adafruit_BBIO.GPIO as GPIO
# import Adafruit_BBIO.PWM as PWM
# import time

# # Verify these match your physical wiring before running
# STBY = "P1_06"
# MOUTH_PWM = "P1_36"
# MOUTH_IN1 = "P1_30"
# MOUTH_IN2 = "P1_32"
# BODY_PWM = "P1_33"
# BODY_IN1 = "P1_26"
# BODY_IN2 = "P1_28"

# # Setup
# #GPIO.setup(STBY, GPIO.OUT)
# GPIO.setup(MOUTH_IN1, GPIO.OUT)
# GPIO.setup(MOUTH_IN2, GPIO.OUT)
# GPIO.setup(BODY_IN1, GPIO.OUT)
# GPIO.setup(BODY_IN2, GPIO.OUT)
# PWM.start(MOUTH_PWM, 0)
# PWM.start(BODY_PWM, 0)


# print("Waking up Billy...")
# #GPIO.output(STBY, GPIO.HIGH) # Enable Driver

# try:
#     print("Mouth Open!")
#     GPIO.output(MOUTH_IN1, GPIO.HIGH)
#     GPIO.output(MOUTH_IN2, GPIO.LOW)
#     PWM.set_duty_cycle(MOUTH_PWM, 100) # Full speed open
#     time.sleep(1)
    
#     print("Mouth Closed!")
#     PWM.set_duty_cycle(MOUTH_PWM, 0) # Release spring
#     time.sleep(1)
    
#     print("Look at Me!")
#     GPIO.output(BODY_IN1, GPIO.HIGH)
#     GPIO.output(BODY_IN2, GPIO.LOW)
#     PWM.set_duty_cycle(BODY_PWM, 100)
#     time.sleep(1)
    
#     print("Wag Tail!")
#     PWM.set_duty_cycle(BODY_PWM, 0)
#     GPIO.output(BODY_IN1, GPIO.LOW)
#     GPIO.output(BODY_IN2, GPIO.HIGH)
#     PWM.set_duty_cycle(BODY_PWM, 100) # Full speed open
#     time.sleep(1)
    
    

# except KeyboardInterrupt:
#     pass

# PWM.stop(MOUTH_PWM)
# PWM.stop(BODY_PWM)
# GPIO.cleanup()