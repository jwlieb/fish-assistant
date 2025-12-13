#!/bin/bash
cd /var/lib/cloud9/fish-assistant/
config-pin P1_36 pwm
config-pin P1_30 gpio
config-pin P1_32 gpio
config-pin P1_26 gpio
config-pin P1_28 gpio
config-pin P1_33 pwm
python3 -m assistant.cli client --port 8001
