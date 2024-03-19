#!/usr/bin/env micropython
"""
(C) Rod Slattery 2024
Main program for CLACKER

"""
from os import remove
from sys import print_exception
from tinyweb import webserver
import aiohttp
from uasyncio import run, get_event_loop, sleep_ms
from helpers import (
    PropertiesFromFiles, wifi_start_access_point, _handle_exception, mac_to_hostname,
    Database, get_mac, file_exists)
from captive_portal import CaptivePortal
from clacker_hardware import Clacker
from machine import Timer
from functools import partial
from micropython import const
import gc

# WLAN_MODE = network.AP_IF  # network.STA_IF
_HOST_BASE_NAME = const('clacker')
_HOSTNAME = mac_to_hostname(_HOST_BASE_NAME)
_DB_FILE = f'db_{_HOSTNAME}.txt'
_HTML_PATH = const("./html")
_LED_STATUS_OFF = const(3500)  # ms
_LED_CLACK_OFF = const(4500)  # ms


HTML = PropertiesFromFiles(_HTML_PATH)  # JIT read html static pages into memory
hw = Clacker()  # represents the Hardware in the Claymore
app = webserver()  # Create web server application
timers = [None] * 4

if hw.fire.value() == hw.PRESSED and hw.btn4.value() == hw.PRESSED:
    # magic key combination to clear out any DB
    # FIRE + BUTTON 4 on START
    if file_exists(_DB_FILE):
        print('RESET-Deleting DB')
        remove(_DB_FILE)

db = Database(_DB_FILE)
db.setdefault('clacker', {}).update({'mac': get_mac()})
db.setdefault('claymores', [{}] * hw.MAX_CLAYMORES)
team = db['clacker'].setdefault('team', hw.team_color)

ssid = mac_to_hostname(f'{_HOST_BASE_NAME}_{team}')
# password = ssid[:-3]  # secure AP takes too long and WDT kicks to reboot
password = None

ip = wifi_start_access_point(ssid=ssid, hostname=_HOSTNAME, password=password)  # turn on our WIFI in AP Mode

if team != hw.team_color:
    # we may have accidentally toggled the team switch, and rebooted
    for led in hw.leds:
        led.set_primary_color(team)
    hw.status.set_primary_color(team)
    hw.team_color = team

hw.status.on()  # Our AP is active, so turn on our status LED in our team color
captive = CaptivePortal(ip)  # DNS server that redirect all DNS queries to our http://ip/

db['clacker'].update({'ip': ip, 'ssid': ssid})
db.flush()

# db.verify_integrity('clacker', 'id', hw.MAX_CLAYMORES)
# db.flush()
print(db)
print(f"pico w IP: http://{ip}:80")
gc.collect()

def led_off(position, _t):
    print(f'led_off {_t}:{position}')
    hw.leds[position].off()
    if timers[position]:
        timers[position].deinit()
        timers[position] = None


async def check_one(claymore_ip, position):
    # send clack via GET to get the device status before we CLACK
    try:
        led_state = hw.leds[position].state
        if not led_state.startswith('OFF'):
            print(f'LED {position} is not OFF: {led_state}')
            if timers[position]:
                timers[position].deinit()
            timers[position] = Timer()
            timers[position].init(mode=Timer.ONE_SHOT, period=_LED_CLACK_OFF, callback=partial(led_off, position))
            return

        async with aiohttp.ClientSession() as session:
            url = f"http://{claymore_ip}/status"
            print(url)
            async with session.get(url) as resp:
                if resp.status == 200:
                    msg = await resp.text()
                    print(f'Resp "{msg=}"')
                    color = 'GREEN'
                    if msg.upper() == 'OPEN':
                        color = 'RED'
                    hw.leds[position].on(color)
                    if timers[position]:
                        timers[position].deinit()
                    timers[position] = Timer()
                    timers[position].init(mode=Timer.ONE_SHOT, period=_LED_STATUS_OFF, callback=partial(led_off, position))
                else:
                    print(resp.status)
    except Exception as e:
        hw.leds[position].off()
        print_exception(e)


def single_press_fire():
    print("single press fire button")
    # check the status of all of the known devices
    gc.collect()
    loop = get_event_loop()
    for position, claymore in enumerate(db['claymores']):
        if not claymore or not claymore.get('ip'):
            print(f'Skip status {position}')
            continue
        loop.create_task(check_one(claymore['ip'], position))


async def double_press_fire():
    print("double press fire button")
    await long_press_fire()


async def fire_one(claymore_ip, position):
    # send clack via POST
    async with aiohttp.ClientSession() as session:
        url = f"http://{claymore_ip}/clack"
        print(url)
        async with session.post(url) as resp:
            if resp.status == 200:
                # msg = await resp.text()
                msg = await resp.text()
                print(f'clack resp: {msg}')
            else:
                print(resp.status)
    hw.leds[position].off()


async def long_press_fire():
    print("long press fire button")
    # scan to see if any LEDs are ready
    gc.collect()
    loop = get_event_loop()
    for position, claymore in enumerate(db['claymores']):
        if not claymore or not claymore.get('ip'):
            print(f'Skip position {position}')
            continue
        led_state = hw.leds[position].get_state()
        if led_state.get('STATE', 'UNKNOWN').startswith('ALTERNATE'):
            loop.create_task(fire_one(claymore['ip'], position))
        else:
            print(f'position {position} Not selected')
    await sleep_ms(5)  # let our fire_one task start


async def ping_one(position, led_callback):
    # ping-pong first
    try:
        claymore_ip = db['claymores'][position].get('ip')  # need try/except in case it is missing/empty
        if not claymore_ip:
            return
        if timers[position]:
            timers[position].deinit()
            timers[position] = None
        gc.collect()
        async with aiohttp.ClientSession() as session:
            url = f"http://{claymore_ip}/ping"
            print(url)
            async with session.get(url) as resp:
                if resp.status == 200:
                    msg = await resp.text()
                    print(f'ping resp: {msg}')
                    if msg.lower() == 'pong':
                        # toggle, or turn off if blinking or alternating
                        led_callback()
                else:
                    print(resp.status)
    except Exception as e:
        hw.leds[position].off()
        print_exception(e)


async def single_press(position):
    print(f'single_press {position}')
    try:
        gc.collect()
        ip = db['claymores'][position].get('ip')
        if not ip:
            return
        loop = get_event_loop()
        loop.create_task(check_one(ip, position))
        await sleep_ms(5)  # let our ping_one task start
    except Exception as e:
        hw.leds[position].off()
        print_exception(e)


async def double_press(position):
    print(f'double_press {position}')
    try:
        loop = get_event_loop()
        # blink the LED
        loop.create_task(ping_one(position, hw.leds[position].blink))
        await sleep_ms(5)  # let our ping_one task start
    except Exception as e:
        hw.leds[position].off()
        print_exception(e)


async def long_press(position):
    print(f'long_press {position}')
    try:
        loop = get_event_loop()
        # alternate the LED
        loop.create_task(ping_one(position, hw.leds[position].alternate_colors))
        await sleep_ms(5)  # let our ping_one task start
    except Exception as e:
        hw.leds[position].off()
        print_exception(e)


def setup_pushbutton(pb, position):
    pb.press_func(single_press, (position, ))
    pb.double_func(double_press, (position, ))
    pb.long_func(long_press, (position, ))


# Index page
@app.route('/')
async def index(_request, response):
    # Start HTTP response with content-type text/html
    print(response.writer.get_extra_info('peername'))

    await response.start_html()
    try:
        state = hw.hw_status()
        html = HTML.index.format(**state)
        # Send actual HTML page
        await response.send(html)
    except Exception as e:
        print_exception(e)


@app.route('/ping')
async def ping(_request, response):
    await response.start_html()
    try:
        # print('ping from:', response.writer.get_extra_info('peername'))
        await response.send('pong')
    except Exception as e:
        print_exception(e)
        await response.send(str(e)), 500


class Register:

    def _update_from_db(self, data, id):
        data.update({
            'id': id,
            'team': db['clacker']['team']})

    def _find_slot_in_db(self, mac):
        first_empty = -1
        for i, claymore in enumerate(db['claymores']):
            try:
                if not claymore:
                    if first_empty < 0:
                        first_empty = i
                elif claymore.get('mac', 'no-mac').lower() == mac.lower():
                    return i, claymore
            except Exception as e:
                print_exception(e)
        return first_empty, {}

    def not_exists(self, msg='unknown mac', err=404):
        return {'message': msg}, err

    def get(self, data, mac):
        """Get detailed information about given claymore's mac"""
        print(f'GET /register/{mac} GET {data}')
        found_i, claymore = self._find_slot_in_db(mac)
        if not claymore:
            return self.not_exists()
        print('Returning:', claymore)
        return claymore

    def post(self, data, mac):
        """create given claymore"""
        print(f'/register/{mac} POST {data}')
        found_i, claymore = self._find_slot_in_db(mac)
        try:
            if found_i < 0:
                print('post here 3')
                return self.not_exists('Clacker FULL', 405)
            if claymore:  # is not empty
                print('post here 4')
                return self.not_exists('mac already exists. Try PUT', 403)
        except Exception as e:
            print_exception(e)

        try:
            self._update_from_db(data, found_i)
            db['claymores'][found_i] = data
            db[mac] = data
            db.flush()
        except Exception as e:
            print_exception(e)
        print('POST returning:', data)
        return data

    def put(self, data, mac):
        """Update given mac"""
        found_i, claymore = self._find_slot_in_db(mac)
        if found_i < 0 or (not claymore):
            return self.not_exists()
        print(f'/register/{mac} PUT {data}')

        self._update_from_db(data, found_i)
        db['claymores'][found_i] = data
        db[mac] = data
        db.flush()
        return data

    def delete(self, data, mac):
        """Delete customer"""
        found_i, claymore = self._find_slot_in_db(mac)
        if found_i < 0 or (not claymore):
            return self.not_exists()
        print(f'/register/{mac} DELETE {data} -> {found_i}')
        del db[mac]
        db['claymores'][found_i] = {}
        db.flush()
        return {'message': 'successfully deleted'}


@app.route('/register')
async def register(_request, response):
    print(response.writer.get_extra_info('peername'))
    await response.start_html()
    # Need to modify some info out of our 'Database'
    try:
        html = HTML.register  # .format(**state)
        # Send actual HTML page
        await response.send(html)
    except Exception as e:
        print_exception(e)


async def main():
    app.add_resource(Register, '/register/<mac>')

    app.run(host='0.0.0.0', port=80, loop_forever=False)

    # add pushbutton actions to the event queue
    hw.pb_fire.press_func(single_press_fire, tuple())
    hw.pb_fire.double_func(double_press_fire, tuple())
    hw.pb_fire.long_func(long_press_fire, tuple())

    for position, pb in enumerate(hw.pushbuttons):
        setup_pushbutton(pb, position)

    loop = get_event_loop()
    loop.set_exception_handler(_handle_exception)
    await captive.add_server(loop)
    print('Looping forever...')
    loop.run_forever()

run(main())
