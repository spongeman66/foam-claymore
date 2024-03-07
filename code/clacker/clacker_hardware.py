import sys
import uasyncio as asyncio
from machine import Pin, Timer, PWM
from dual_led import DualLED
from helpers import get_wifi_status
from hardware import *
from primitives import Pushbutton

# # Output pins
# # Output, Normally Low: LED 0 == Off, 1 == On
# STATUS_RED_GP = 9
# STATUS_GRN_GP = 4
# LED1_RED_GP   = 8
# LED1_GRN_GP   = 3
# LED2_RED_GP   = 7
# LED2_GRN_GP   = 2
# LED3_RED_GP   = 6
# LED3_GRN_GP   = 1
# LED4_RED_GP   = 5
# LED4_GRN_GP   = 0
#
# # Input pins
# # Input, Normally High: 0 == PRESSED, 1 == NOT-PRESSED
# BTN1_GP       = 13
# BTN2_GP       = 12
# BTN3_GP       = 11
# BTN4_GP       = 10
# BTN_FIRE_GP   = 21
# SW_AB_GP      = 22


class Clacker:
    LED = ('OFF', 'ON')
    SWITCH = ('PRESSED', 'OFF')
    TEAMS = tuple(DualLED.COLORS)
    PRESSED = 0
    NOT_PRESSED = 1
    MAX_CLAYMORES = 4

    def __init__(self):
        # unique hardware
        self.fire = Pin(BTN_FIRE_GP, Pin.IN, Pin.PULL_UP)
        self.pb_fire = Pushbutton(self.fire, suppress=True, sense=self.NOT_PRESSED)
        self.sw_ab = Pin(SW_AB_GP, Pin.IN, Pin.PULL_UP)
        self.team_color = self.TEAMS[self.sw_ab.value()]
        self.status = DualLED(STATUS_RED_GP, STATUS_GRN_GP, self.team_color)

        # similar hardware that needs to be indexed
        self.btn1 = Pin(BTN1_GP, Pin.IN, Pin.PULL_UP)
        self.btn2 = Pin(BTN2_GP, Pin.IN, Pin.PULL_UP)
        self.btn3 = Pin(BTN3_GP, Pin.IN, Pin.PULL_UP)
        self.btn4 = Pin(BTN4_GP, Pin.IN, Pin.PULL_UP)

        self.pb1 = Pushbutton(self.btn1, suppress=True, sense=self.NOT_PRESSED)
        self.pb2 = Pushbutton(self.btn2, suppress=True, sense=self.NOT_PRESSED)
        self.pb3 = Pushbutton(self.btn3, suppress=True, sense=self.NOT_PRESSED)
        self.pb4 = Pushbutton(self.btn4, suppress=True, sense=self.NOT_PRESSED)

        self.led1 = DualLED(LED1_RED_GP, LED1_GRN_GP, self.team_color)
        self.led2 = DualLED(LED2_RED_GP, LED2_GRN_GP, self.team_color)
        self.led3 = DualLED(LED3_RED_GP, LED3_GRN_GP, self.team_color)
        self.led4 = DualLED(LED4_RED_GP, LED4_GRN_GP, self.team_color)

        # make lists of similar items
        self.buttons = [self.btn1, self.btn2, self.btn3, self.btn4]
        self.pushbuttons = [self.pb1, self.pb2, self.pb3, self.pb4]
        self.leds = [self.led1, self.led2, self.led3, self.led4]
        asyncio.create_task(self.test())
        
    async def test(self):
        self.status.alternate_colors()
        for led in self.leds:
            led.alternate_colors()
        await asyncio.sleep(1)
        self.status.on()
        for led in self.leds:
            led.on()
        await asyncio.sleep(1)
        self.status.off()
        for led in self.leds:
            led.off()

    def other_team(self):
        ot = list(self.TEAMS)
        ot.remove(self.team_color)
        return ot[0]

    # async def status(self):
    def hw_status(self):
        # this should all be 'fast' everything is HW/in memory
        status = get_wifi_status()
        status.update({
            'fire': self.SWITCH[self.fire.value()],   # 0->PRESSED, 1->OFF
            'sw_ab': self.TEAMS[self.sw_ab.value()],  # 0->PRESSED, 1->OFF
            'team_color': self.team_color,
            'status': self.status.get_state(),
            'btn_1': self.SWITCH[self.btn1.value()],  # 0->PRESSED, 1->OFF
            'btn_2': self.SWITCH[self.btn2.value()],  # 0->PRESSED, 1->OFF
            'btn_3': self.SWITCH[self.btn3.value()],  # 0->PRESSED, 1->OFF
            'btn_4': self.SWITCH[self.btn4.value()],  # 0->PRESSED, 1->OFF
            'led_1': self.led1.get_state(),
            'led_2': self.led2.get_state(),
            'led_3': self.led3.get_state(),
            'led_4': self.led4.get_state()
        })
        return status

if __name__ == '__main__':

    async def run_hardware_status(hw, interval=3000):
        while True:  # Poll hardware and update LEDs
            try:
                await asyncio.sleep_ms(interval)
                status = hw.hw_status()
                hw.team_color = DualLED.COLORS[hw.sw_ab.value()]
                hw.status.set_primary_color(hw.team_color)
                for led in hw.leds:
                    led.set_primary_color(hw.team_color)
                    led.toggle()

            except Exception as e:
                sys.print_exception(e)
                await asyncio.sleep_ms(interval)

    hw = Clacker()
    loop = asyncio.get_event_loop()
    loop.create_task(run_hardware_status(hw, 3000))
    