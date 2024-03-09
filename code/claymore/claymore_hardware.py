import sys
import uasyncio as asyncio
from machine import Pin, Timer, PWM
from dual_led import DualLED
from hardware import *
# # Output pins
# SIGNAL_RED_GPIO = 13  # Output, Normally Low: RED   Signal LED 0 == Off, 1 == On
# SIGNAL_GRN_GPIO = 14  # Output, Normally Low: GREEN Signal LED 0 == Off, 1 == On
# ARMED_RED_GPIO = 16   # Output, Normally Low: RED   Armed LED 0 == Off, 1 == On
# ARMED_GRN_GPIO = 19   # Output, Normally Low: GREEN Armed LED 0 == Off, 1 == On
#
# # Input pins
# STANDALONE_GPIO = 9   # Input, Normally High: 0 == APMode(STA_AP Standalone), 1 == Scan and Connect to AP (STA_IF)
# AB_GPIO = 10          # Input, Normally High: 0 == Team A (ORANGE?), 1 == Team B (BLUE?)
# DOOR_GPIO = 21        # Input, Normally High: 0 == Door CLOSED, 1 == Door OPEN
#
# # PWM pins
# ServoMax = 8400
# ServoMin = 1400
# ServoFire = ServoMin
# ServoReady = ServoMax
# SERVO_GPIO = 22        # PWM to control trigger servo


class Claymore:
    TRIGGER_RESET = 3500  # Trigger automatically resets after # milliseconds
    DOOR = ['CLOSED', 'OPEN']
    TEAM = DualLED.COLORS
    LED = ['OFF', 'ON']

    def __init__(self):
        self.door = Pin(DOOR_GPIO, Pin.IN, Pin.PULL_UP)
        self.team = Pin(AB_GPIO, Pin.IN, Pin.PULL_UP)
        self.ap_mode = Pin(STANDALONE_GPIO, Pin.IN, Pin.PULL_UP)
        self.team_color = DualLED.COLORS[self.team.value()]
        self.armed_led = DualLED(ARMED_RED_GPIO, ARMED_GRN_GPIO, self.team_color)
        self.signal_led = DualLED(SIGNAL_RED_GPIO, SIGNAL_GRN_GPIO, self.team_color)

        self.trigger = PWM(Pin(SERVO_GPIO))
        self.trigger.freq(50)
        self.timer = None
        self.servo_position = None
        self.set_trigger_position(ServoReady)
        asyncio.create_task(self.test())

    async def test(self):
        self.armed_led.alternate_colors()
        self.signal_led.alternate_colors()
        await asyncio.sleep(1)
        self.armed_led.on()
        self.signal_led.on()
        await asyncio.sleep(1)
        self.armed_led.off()
        self.signal_led.off()

    def set_trigger_position(self, position):
        position = ServoMin if position < ServoMin else position
        position = ServoMax if position > ServoMax else position
        self.servo_position = position
        self.trigger.duty_u16(position)

    def fire_trigger(self):
        print("fire_trigger")
        signal_state = self.signal_led.state
        armed_state = self.armed_led.state

        def __reset_trigger(_t):
            print("__reset_trigger callback")
            self.set_trigger_position(ServoReady)
            self.signal_led.restore_state(state=signal_state)
            self.armed_led.restore_state(state=armed_state)
            if self.timer:
                self.timer = None

        self.set_trigger_position(ServoFire)
        self.signal_led.alternate_colors()
        self.armed_led.alternate_colors()
        if self.timer:
            self.timer.deinit()
        self.timer = Timer()
        self.timer.init(
            mode=Timer.ONE_SHOT, period=int(self.TRIGGER_RESET), callback=__reset_trigger)

    def status(self):
        # status = get_wifi_status()
        status = {
            'door': self.DOOR[self.door.value()],  # 0->CLOSED, 1->OPEN
            'team': self.TEAM[self.team.value()],
            'team_color': self.team_color,
            'standalone': str(bool(self.ap_mode.value() == 0)),
            'armed': self.armed_led.get_state(),
            'signal': self.signal_led.get_state(),
            'trigger': "READY" if self.servo_position == ServoReady else "FIRING"
        }
        print(status)
        return status


if __name__ == '__main__':
    async def run_hardware_status(self, interval=3000):
        while True:  # Poll hardware and update LEDs
            try:
                await asyncio.sleep_ms(interval)
                status = await self.status()
                self.team_color = DualLED.COLORS[self.team.value()]
                self.armed_led.set_primary_color(self.team_color)
                self.signal_led.set_primary_color(self.team_color)
                if status['door'] == 'CLOSED':
                    self.armed_led.on()
                else:
                    self.armed_led.off()

            except Exception as e:
                sys.print_exception(e)
                await asyncio.sleep_ms(interval)

    hw = Claymore()
    loop = asyncio.get_event_loop()
    loop.create_task(run_hardware_status(hw, 3000))
