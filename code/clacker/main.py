#!/usr/bin/env micropython
"""
(C) Rod Slattery 2024
Main program for CLACKER

"""
import os
import sys
from tinyweb import webserver
import network
import uasyncio as asyncio
from helpers import (
    PropertiesFromFiles, wifi_start_access_point, _handle_exception, mac_to_hostname,
    Database, get_mac, file_exists)
from captive_portal import CaptivePortal
from clacker_hardware import Clacker


# WLAN_MODE = network.AP_IF  # network.STA_IF

HOST_BASE_NAME = 'clacker'
HTML_PATH = "./html"
HTML = PropertiesFromFiles(HTML_PATH)  # JIT read html static pages into memory
hw = Clacker()  # represents the Hardware in the Claymore
app = webserver()  # Create web server application
hostname = mac_to_hostname(f'{HOST_BASE_NAME}')
db_file = f'db_{hostname}.txt'

if hw.fire.value() == hw.PRESSED and hw.btn4.value() == hw.PRESSED:

    # magic key combination to clear out any DB
    # FIRE + BUTTON 4 on START
    if file_exists(db_file):
        print('RESET-Deleting DB')
        os.remove(db_file)

db = Database(db_file)
db.setdefault('clacker', {}).update({'mac': get_mac(), 'hostname': hostname})
db.setdefault('claymores', [{}] * hw.MAX_CLAYMORES)
team = db['clacker'].setdefault('team', hw.team_color)

if team != hw.team_color:
    # we may have accidentally toggled the team switch, and rebooted
    for led in hw.leds:
        led.set_primary_color(team)
    hw.status.set_primary_color(team)
    hw.team_color = team

ssid = mac_to_hostname(f'{HOST_BASE_NAME}_{team}')
ip = wifi_start_access_point(ssid=ssid, hostname=hostname)  # turn on our WIFI in AP Mode

hw.status.on()  # Our AP is active, so turn on our status LED in our team color

captive = CaptivePortal(ip)  # DNS server that redirect all DNS queries to our http://ip/

db['clacker'].update({'ip': ip, 'ssid': ssid})
db.flush()

# db.verify_integrity('clacker', 'id', hw.MAX_CLAYMORES)
# db.flush()
print(db)
print(f"pico w IP: http://{ip}:80")
print(f"pico w IP: http://{network.hostname()}:80")


def single_press_fire():
    print("single press fire button")


def double_press_fire():
    print("double press fire button")


def long_press_fire():
    print("long press fire button")


def single_press(position):
    # toggle, or turn off if blinking or alternating
    hw.leds[position].toggle()


def double_press(position):
    # blink the LED
    hw.leds[position].blink()


def long_press(position):
    # alternate the LED
    hw.leds[position].alternate_colors()


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
        sys.print_exception(e)


@app.route('/ping')
async def ping(_request, response):
    await response.start_html()
    try:
        print('ping from:', response.writer.get_extra_info('peername'))
        await response.send('pong')
    except Exception as e:
        sys.print_exception(e)
        await response.send(str(e)), 500


class Register:

    def _update_from_db(self, data, id):
        data.update({
            'id': id,
            'clacker_ip': db['clacker']['ip'],
            'clacker_mac': db['clacker']['mac'],
            'clacker_hostname': db['clacker']['hostname'],
            'team': db['clacker']['team']})

    def _find_slot_in_db(self, mac):
        first_empty = -1
        for i, claymore in enumerate(db['claymores']):
            print(f"{i} {claymore}")
            if not claymore:
                print("here1 {i}")
                if first_empty < 0:
                    first_empty = i
            elif claymore.get('mac', 'no-mac').lower() == mac.lower():
                print(f"here2 {i}")
                return i, claymore
        print(f"Not Found. returning {first_empty} ")
        return first_empty, {}

    def not_exists(self, msg='unknown mac', err=404):
        return {'message': msg}, err

    def get(self, data, mac):
        """Get detailed information about given claymore's mac"""
        found_i, claymore = self._find_slot_in_db(mac)
        if not claymore:
            return self.not_exists()
        print(f'/register/{mac} GET {data} -> {claymore}')
        return claymore

    def post(self, data, mac):
        """create given claymore"""
        found_i, claymore = self._find_slot_in_db(mac)
        if found_i < 0:
            return self.not_exists('Clacker FULL', 405)
        if claymore:  # is not empty
            return self.not_exists('mac already exists. Try PUT', 403)
        print(f'/register/{mac} POST {data}')

        self._update_from_db(data, found_i)
        db['claymores'][found_i] = data
        db[mac] = data
        db.flush()
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
        print(f'/register/{mac} DELETE {data} -> {db[mac]}')
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
        sys.print_exception(e)


async def run():
    app.add_resource(Register, '/register/<mac>')

    app.run(host='0.0.0.0', port=80, loop_forever=False)

    # add pushbutton actions to the event queue
    hw.pb_fire.press_func(single_press_fire, tuple())
    hw.pb_fire.double_func(double_press_fire, tuple())
    hw.pb_fire.long_func(long_press_fire, tuple())

    for position, pb in enumerate(hw.pushbuttons):
        print('Setting position:', position)
        setup_pushbutton(pb, position)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_handle_exception)
    await captive.add_server(loop)
    print('Looping forever...')
    loop.run_forever()

asyncio.run(run())
