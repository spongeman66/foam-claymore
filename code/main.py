#!/usr/bin/env micropython
"""
(C) Rod Slattery 2024
"""
import sys
from tinyweb import webserver
import network
import uasyncio as asyncio
from helpers import PropertiesFromFiles, wifi_start_access_point, _handle_exception, mac_to_hostname
from captive_portal import CaptivePortal
from claymore_hardware import Claymore

# WLAN_MODE = network.AP_IF  # network.STA_IF
HOST_BASE_NAME = 'claymore'
HTML_PATH = "./html"

HTML = PropertiesFromFiles(HTML_PATH)  # JIT read html static pages into memory
hw = Claymore()  # represents the Hardware in the Claymore
app = webserver()  # Create web server application


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


async def run():
    hostname = mac_to_hostname(base=HOST_BASE_NAME)
    ip = wifi_start_access_point(ssid=hostname, hostname=hostname)
    print(f"pico w IP: http://{ip}:80")
    print(f"pico w IP: http://{network.hostname()}:80")
    app.run(host='0.0.0.0', port=80, loop_forever=False)

    captive = CaptivePortal(ip)
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_handle_exception)
    await captive.add_server(loop)
    await hw.add_server(loop)
    print('Looping forever...')
    loop.run_forever()

if __name__ == '__main__':
    asyncio.run(run())
    # To test your server:
    # - Terminal:
    #   $ curl http://localhost:8081
    #   or
    #   $ curl http://localhost:8081/table
    #
    # - Browser:
    #   http://localhost:8081
    #   http://localhost:8081/table
    #
    # - To test HTTP redirection:
    #   curl http://localhost:8081/redirect -v
