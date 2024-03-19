#!/usr/bin/env micropython
"""
(C) Rod Slattery 2024
Main program for CLAYMORE
"""
import errno
import network
import uasyncio as asyncio
from os import remove
from machine import (reset, WDT, reset_cause, PWRON_RESET, WDT_RESET)
from micropython import const
from time import sleep
from sys import print_exception
from tinyweb import webserver
from aiohttp import ClientSession
from helpers import (
    PropertiesFromFiles, wifi_start_access_point, wifi_connect_to_access_point,
    _handle_exception, mac_to_hostname, Database, scan_wifi, get_mac, WLAN_STATUS)
# from captive_portal import CaptivePortal
from claymore_hardware import Claymore
from gc import collect


# WLAN_MODE = network.AP_IF  # network.STA_IF
HOST_BASE_NAME = const('claymore')
HTML_PATH = const("./html")
WDT_TIMEOUT = const(8000)
IP_TIMEOUT = const(6000)  # Must be less than WDT

RESET_CAUSES = {
    PWRON_RESET: 'PWRON_RESET',
    WDT_RESET: 'WDT_RESET'
}

MY_WDT = None
HTML = PropertiesFromFiles(HTML_PATH)  # JIT read html static pages into memory
hw = Claymore()  # represents the Hardware in the Claymore
app = webserver()  # Create web server application

hostname = mac_to_hostname(base=HOST_BASE_NAME)
db_file = f'db_{hostname}.txt'

# what is our magic button sequence?
# for now power on with the door open.
# Then double-click the door button

db = Database(db_file)
db.setdefault('claymore', {}).update({'mac': get_mac()})  # , 'hostname': hostname})
team = db['claymore'].setdefault('team', hw.team_color)
if team != hw.team_color:
    # we may have accidentally toggled the team switch, and rebooted
    hw.armed_led.set_primary_color(team)
    hw.signal_led.set_primary_color(team)
    hw.team_color = team

if hw.pb_door:
    def reset_db():
        print('RESET-Deleting DB')
        remove(db_file)
        reset()

    hw.pb_door.multi_click_func(5, reset_db, tuple())


print(f"Reset Cause: {reset_cause()} {RESET_CAUSES[reset_cause()]}")
if reset_cause() in [PWRON_RESET]:
    print("Normal Reset Cause.")
elif reset_cause() in [WDT_RESET]:
    print("REBOOT DUE TO WATCH DOG TIMER.")
else:
    print("UNKNOWN RESET CAUSE")

# scan for wifi clacker
available_wifi = []
while not available_wifi:
    if db.get('clacker', {}).get('ssid'):
        # is old clacker available?
        available_wifi = scan_wifi([db['clacker']['ssid']])
        if not available_wifi:
            print(f"Our old clacker: {db['clacker']['ssid']} is not in the current list!")
            #  db.pop('clacker', None)  # Do we really want to do this?
            # must match both 'clacker' and team color
            available_wifi = scan_wifi(['clacker', team])
    else:
        available_wifi = scan_wifi(['clacker', team])
    if not available_wifi:
        print(f"No suitable APs available for {db['clacker']['ssid']} or team {team}")
        sleep(3)

# we got one. Try to connect.
for ap in available_wifi:
    print(ap)
    password = None
    if ap['security'] != 0:
        # convention is the password = the ssid - the 2 characters at the end
        password = ap['ssid'][:-3]
    try:
        ip, clacker_ip = wifi_connect_to_access_point(ssid=ap['ssid'], password=password)
        db['claymore'].update({'ip': ip})  # , 'url': f'http://{ip}'})
        db.setdefault('clacker', {}).update({'ssid': ap['ssid'], 'password': password})
        db['clacker'].update({'ip': clacker_ip, 'url': f"http://{clacker_ip}"})
        break
    except Exception as e:
        print_exception(e)
db.flush()

print(f"pico w IP: http://{ip}:80")
print(f"pico w IP: http://{network.hostname()}:80")

# Only need this if we decide to be an AP!
# captive = CaptivePortal(ip)
captive = None
url_base = db['clacker']['url']


def rescan_wifi(ssid):
    available_wifi = scan_wifi([ssid])
    print(f'\nRescan APs found:\n{available_wifi}')
    return available_wifi


# Index page
@app.route('/')
async def index(_request, response):
    # Start HTTP response with content-type text/html
    await response.start_html()
    try:
        state = await hw.status()
        print(state)
        html = HTML.fire.format(**state)
        # Send actual HTML page
        await response.send(html)
    except Exception as e:
        print_exception(e)
        return str(e), 500


@app.route('/fire')
async def fire_get(_request, response):
    try:
        # Start HTTP response with content-type text/html
        hw.fire_trigger()
        await response.redirect('/')
    except Exception as e:
        print_exception(e)
        return str(e), 500


@app.route('/status')
async def status(_request, response):
    await response.start_html()
    try:
        # Start HTTP response with content-type text/html
        status = hw.status()
        state = status['door']
        print(state)
        # Send actual HTML page
        await response.send(state)
    except Exception as e:
        print_exception(e)
        return str(e), 500


@app.route('/ping')
async def ping(_request, response):
    await response.start_html()
    try:
        collect()  # the garbage
        # print('ping from:', response.writer.get_extra_info('peername'))
        await response.send('pong')
    except Exception as e:
        print_exception(e)
        await response.send(str(e)), 500


class Clack:
    async def get(self, data):
        print(f'/clack GET {data}')
        try:
            status = await hw.status()
            data.update(status)  #  = {'door': status['door']}
            print(data)
            # print(f'Returning:\n{json.dumps(status)}')
            return data
        except Exception as e:
            print_exception(e)
            return str(e), 500

    async def post(self, data):
        print(f'/clack POST {data}')
        try:
            hw.fire_trigger()
            print("fire_trigger 5")
            return 'FIRE'
        except Exception as e:
            print_exception(e)
            return str(e), 500


async def ping_forever(interval_ms=None):
    interval_ms = interval_ms or IP_TIMEOUT
    err_do_reconnect = True
    while True:
        MY_WDT.feed()
        collect()  # the garbage
        MY_WDT.feed()
        await asyncio.sleep_ms(int(interval_ms/2))
        MY_WDT.feed()
        await asyncio.sleep_ms(int(interval_ms/2))
        MY_WDT.feed()
        try:
            wlan_status = network.WLAN().status()
            if (wlan_status != 3) or err_do_reconnect:  # NOT LINK_UP or failed in some other way
                print('wlanstatus =', WLAN_STATUS.get(wlan_status, f'UNKNOWN{wlan_status}'))
                MY_WDT.feed()
                avail = rescan_wifi(db['clacker']['ssid'])
                MY_WDT.feed()
                if avail:
                    # try reconnect (This may not play well with asyncio)
                    ip, clacker_ip = wifi_connect_to_access_point(
                        ssid=db['clacker']['ssid'], password=db['clacker']['password'])
                    MY_WDT.feed()
                    db['claymore'].update({'ip': ip})  # , 'url': f'http://{ip}'})
                    db['clacker'].update({'ip': clacker_ip, 'url': f"http://{clacker_ip}"})
                    db['claymore']['id'] = await get_registered(db)
                    db.flush()
                    err_do_reconnect = False

        except Exception as e:
            print_exception(e)
        MY_WDT.feed()
        try:
            pong, _ = await send_ping(f"{db['clacker']['url']}/ping")
            MY_WDT.feed()
            print(pong)
            if pong.lower() == 'pong':
                if not hw.timer:  # we may be doing something else...
                    hw.signal_led.on()
                    if not hw.armed_led.state.startswith('COUNT'):
                        hw.armed_led.count_number(db['claymore']['id'] + 1)
        except asyncio.TimeoutError as e:
            # ping has timed out... We must be losing wifi connection
            MY_WDT.feed()
            print('TimeoutError during Ping:')
            hw.signal_led.blink()
            print_exception(e)
            err_do_reconnect = True
        except OSError as e:
            print(f'OSError during Ping: {e.errno=} {e.value=}')
            hw.signal_led.blink()
            print_exception(e)
            if e.errno == errno.ENOMEM:
                print('OOM')
                reset()
            err_do_reconnect = True
            MY_WDT.feed()
        except Exception as e:
            print('EXCEPTION during Ping')
            MY_WDT.feed()
            hw.signal_led.alternate_colors()
            print_exception(e)
            err_do_reconnect = True


async def send_ping(url):
    # ping with a shorter timeout if the wifi has dropped
    async with ClientSession() as session:
        # add a timeout in case our wifi connection has gone bad
        # let the timeout exception bubble up so it can be handled
        MY_WDT.feed()
        ses = session.get(url)
        resp = await asyncio.wait_for(ses.__aenter__(), timeout=IP_TIMEOUT)
        MY_WDT.feed()
        pong = await asyncio.wait_for(resp.text(), timeout=IP_TIMEOUT)
        MY_WDT.feed()
        await asyncio.wait_for(ses.__aexit__(None, None, None), timeout=IP_TIMEOUT)
        MY_WDT.feed()
        return pong, resp.status


async def send_rest(verb, url, **kwargs):
    MY_WDT.feed()
    data = None
    async with ClientSession() as session:
        ses = session.request(verb, url, **kwargs)
        resp = await asyncio.wait_for(ses.__aenter__(), timeout=IP_TIMEOUT)
        MY_WDT.feed()
        if resp.status == 200:
            data = await asyncio.wait_for(resp.json(), timeout=IP_TIMEOUT)
            MY_WDT.feed()
        await asyncio.wait_for(ses.__aexit__(None, None, None), timeout=IP_TIMEOUT)
        MY_WDT.feed()
        return data, resp.status


async def get_registered(db):
    await send_ping(f"{db['clacker']['url']}/ping")  # may cause a timeout if no response
    url = f"{db['clacker']['url']}/register/{db['claymore']['mac']}"
    print(f'Getting registered: {url}')
    for verb in ['GET', 'POST', 'PUT', 'GET']:
        if verb == 'GET':
            data, resp_status = await send_rest(verb, url)
        else:
            data, resp_status = await send_rest(verb, url, json=db['claymore'])
        print(f'{verb} {url} -> {resp_status}:{data}')
        if resp_status == 200:
            if 'id' in data:
                db['claymore'].update(data)
                db.flush()
                MY_WDT.feed()
                return data['id']
        else:
            print(data)


async def run():
    # ping-pong our clacker
    db.setdefault('clacker', {}).update({'ssid': ap['ssid'], 'password': password, 'security': ap['security']})
    db['clacker'].update({'ip': clacker_ip, 'url': f"http://{clacker_ip}"})
    db.flush()

    app.add_resource(Clack, '/clack')
    app.run(host='0.0.0.0', port=80, loop_forever=False)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_handle_exception)
    if captive:
        await captive.add_server(loop)
    loop.create_task(ping_forever())
    print('Looping forever...')
    loop.run_forever()

if __name__ == '__main__':
    print("Starting WDT")
    MY_WDT = WDT(timeout=WDT_TIMEOUT)
    asyncio.run(run())
