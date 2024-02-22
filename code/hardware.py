ServoMax = 8400
ServoMin = 1400
ServoFire = ServoMin
ServoReady = ServoMax

# Planned for this, but messed up the soldering job!
# ARMED_RED_GPIO = 17   # Output, Normally Low: RED Armed LED 0 == Off, 1 == On
# ARMED_GRN_GPIO = 18   # Output, Normally Low: RED Armed LED 0 == Off, 1 == On

# Hard Wired Pins and their intent
# Note, if BOTH pins to the same LED are ON, it will glow RED ONLY
# To Blink RED-GREEN, just hold GREEN ON, and toggle RED on/off/on/off

# Output pins
SIGNAL_RED_GPIO = 13  # Output, Normally Low: RED   Signal LED 0 == Off, 1 == On
SIGNAL_GRN_GPIO = 14  # Output, Normally Low: GREEN Signal LED 0 == Off, 1 == On

ARMED_RED_GPIO = 16   # Output, Normally Low: RED   Armed LED 0 == Off, 1 == On
ARMED_GRN_GPIO = 19   # Output, Normally Low: GREEN Armed LED 0 == Off, 1 == On

# Input pins
STANDALONE_GPIO = 9   # Input, Normally High: 0 == APMode(STA_AP Standalone), 1 == Scan and Connect to AP (STA_IF)
AB_GPIO = 10          # Input, Normally High: 0 == Team A (ORANGE?), 1 == Team B (BLUE?)
DOOR_GPIO = 21        # Input, Normally High: 0 == Door CLOSED, 1 == Door OPEN

# PWM pins
SERVO_GPIO = 22        # PWM to control trigger servo

# ADC pins
# INTERNAL_VOLTAGE_ADC = 29 # GPIO29 is Analog to Digital Converter: ADC input proportional to Vsys
# conversion_factor = 3.3 / (65535)
# adc_Vsys = machine.ADC(3)
# Vsys = adc_Vsys.read_u16() * 3.0 * conversion_factor. #  Multiply by 3 because resistor divider (200k//100K)
# NOTE:  On Pico W you need to disable the wifi /bluetooth to read Vsys
