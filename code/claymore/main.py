#!/usr/bin/env micropython
"""
(C) Rod Slattery 2024
Main program for CLAYMORE
"""
import errno
import machine
import sys
from tinyweb import webserver
import network
import uasyncio as asyncio
import aiohttp
from helpers import (
    PropertiesFromFiles, wifi_start_access_point, wifi_connect_to_access_point, _handle_exception, mac_to_hostname,
    Database, scan_wifi, get_mac, get_wifi_status)
# from captive_portal import CaptivePortal
from claymore_hardware import Claymore


# WLAN_MODE = network.AP_IF  # network.STA_IF
HOST_BASE_NAME = 'claymore'
HTML_PATH = "./html"

HTML = PropertiesFromFiles(HTML_PATH)  # JIT read html static pages into memory
hw = Claymore()  # represents the Hardware in the Claymore
app = webserver()  # Create web server application

hostname = mac_to_hostname(base=HOST_BASE_NAME)
db_file = f'db_{hostname}.txt'

# what is our magic button sequence?

db = Database(db_file)
db.setdefault('claymore', {}).update({'mac': get_mac(), 'hostname': hostname})
team = db['claymore'].setdefault('team', hw.team_color)
if team != hw.team_color:
    # we may have accidentally toggled the team switch, and rebooted
    hw.armed_led.set_primary_color(team)
    hw.signal_led.set_primary_color(team)
    hw.team_color = team

# scan for wifi clacker
available_wifi, _ = scan_wifi(['clacker', team])
print(f'\n\n{team} Select from:')
if db.get('clacker', {}).get('ssid'):
    target_ssid = db['clacker']['ssid']
    found_clacker = ([
        ap for ap in available_wifi
        if ap.get('ssid').lower() == target_ssid.lower()] or [None])[0]
    if not found_clacker:
        print(f"Our old clacker: {target_ssid} is not in the current list!")
        db.pop('clacker', None)
    else:
        # we found OUR clacker in the list! Make sure it is the ONLY one!
        available_wifi = [found_clacker]

for ap in available_wifi:
    print(ap)
    password = None
    if ap['security'] != 0:
        # convention is the password is the ssid - the 2 characters at the end
        password = ap['ssid'][:-3]
    try:
        ip, clacker_ip = wifi_connect_to_access_point(ssid=ap['ssid'], password=password, security=ap['security'])
        db['claymore'].update({'ip': ip, 'url': f'http://{ip}'})
        db.setdefault('clacker', {}).update({'ssid': ap['ssid'], 'password': password, 'security': ap['security']})
        db['clacker'].update({
            'ip': clacker_ip,
            'url': f"http://{clacker_ip}"})
        break
    except Exception as e:
        sys.print_exception(e)
db.flush()

print(f"pico w IP: http://{ip}:80")
print(f"pico w IP: http://{network.hostname()}:80")

# Only need this if we decide to be an AP!
# captive = CaptivePortal(ip)
captive = None
mac = db['claymore']['mac']
url_base = db['clacker']['url']


# Index page
@app.route('/')
async def fire(_request, response):
    # Start HTTP response with content-type text/html
    await response.start_html()
    try:
        state = await hw.status()
        print(state)
        html = HTML.fire.format(**state)
        # Send actual HTML page
        await response.send(html)
    except Exception as e:
        sys.print_exception(e)


@app.route('/fire')
async def redirect(_request, response):
    try:
        # Start HTTP response with content-type text/html
        hw.fire_trigger()
        await response.redirect('/')
    except Exception as e:
        sys.print_exception(e)

async def ping_forever(interval=5):
    url = f"{url_base}/ping"
    while True:
        await asyncio.sleep(interval)
        try:
            print('wlanstatus=', get_wifi_status()['wlanstatus'])
        except Exception as e:
            sys.print_exception(e)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    print(await resp.text(), resp.status)
        except OSError as e:
            print(f'OSError during Ping: {e.errno=} {e.value}')
            sys.print_exception(e)
            if e.errno == errno.ENOMEM:
                machine.reset()
        except Exception as e:
             print('EXCEPTION during Ping')
             sys.print_exception(e)


async def run():
    # ping-pong our clacker
    db.setdefault('clacker', {}).update({'ssid': ap['ssid'], 'password': password, 'security': ap['security']})
    db['clacker'].update({
        'ip': clacker_ip,
        'url': f"http://{clacker_ip}"})
    db.flush()
    # mac = db['claymore']['mac']
    # url_base = db['clacker']['url']

    async with aiohttp.ClientSession() as session:
        url = f"{url_base}/ping"
        print(url)
        async with session.get(url) as resp:
            print(resp.status)
            print(await resp.text())

    async with aiohttp.ClientSession() as session:
        url = f"{url_base}/register/{mac}"
        print(url)
        async with session.get(url) as resp:
            print(resp.status)
            if resp.status == 200:
                print(await resp.json())
            else:
                print(await resp.text())

    async with aiohttp.ClientSession() as session:
        url = f"{url_base}/register/{mac}"
        print(f'POST {url} {db["claymore"]}')
        async with session.post(url, json=db['claymore']) as resp:
            print(resp.status)
            if resp.status == 200:
                print(await resp.json())
            else:
                print(await resp.text())

    async with aiohttp.ClientSession() as session:
        url = f"{url_base}/register/{mac}"
        print(f'PUT {url} {db["claymore"]}')
        async with session.put(url, json=db['claymore']) as resp:
            print(resp.status)
            if resp.status == 200:
                print(await resp.json())
            else:
                print(await resp.text())

    async with aiohttp.ClientSession() as session:
        url = f"{url_base}/register/{mac}"
        print(url)
        async with session.get(url) as resp:
            print(resp.status)
            if resp.status == 200:
                print(await resp.json())
            else:
                print(await resp.text())

    app.run(host='0.0.0.0', port=80, loop_forever=False)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_handle_exception)
    if captive:
        await captive.add_server(loop)
    loop.create_task(ping_forever())
    print('Looping forever...')
    loop.run_forever()

if __name__ == '__main__':
    asyncio.run(run())
