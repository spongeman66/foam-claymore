#!/usr/bin/env micropython
"""
Combines tinyweb async server with CaptivePortal async dns server
"""
import tinyweb
import network
import uasyncio as asyncio
from helpers import wifi_start_access_point, _handle_exception, mac_to_hostname
from captive_portal import CaptivePortal

WLAN_MODE = network.AP_IF  # network.STA_IF
HOST_BASE_NAME = 'tiny_hello_world'

# Create web server application
app = tinyweb.webserver()


# Index page
@app.route('/')
async def index(_request, response):
    # Start HTTP response with content-type text/html
    await response.start_html()
    # Send actual HTML page
    await response.send('<html><body><h1>Hello, world! (<a href="/table">table</a>)</h1></html>\n')


# HTTP redirection
@app.route('/redirect')
async def redirect(_request, response):
    # Start HTTP response with content-type text/html
    await response.redirect('/')


# Another one, more complicated page
@app.route('/table')
async def table(_request, response):
    # Start HTTP response with content-type text/html
    await response.start_html()
    await response.send(
        '<html><body><h1>Simple table</h1>'
        '<table border=1 width=400>'
        '<tr><td>Name</td><td>Some Value</td></tr>')
    for i in range(10):
        await response.send(f'<tr><td>Name{i}</td><td>Value{i}</td></tr>')
    await response.send('</table></html>')


async def run():
    hostname = mac_to_hostname(base=HOST_BASE_NAME)
    ip = wifi_start_access_point(ssid=hostname, hostname=hostname)
    print(f"pico w IP: http://{ip}:80")
    print(f"pico w IP: http://{network.hostname()}:80")
    # add our app to the event loop, but don't start looping forever
    app.run(host='0.0.0.0', port=80, loop_forever=False)
    # Create an instance of the DNS server with our IP address
    captive = CaptivePortal(ip)
    loop = await captive.add_server()  # add our DNS server to the event loop
    loop.set_exception_handler(_handle_exception)
    print('Looping forever...')
    loop.run_forever()

if __name__ == '__main__':
    asyncio.run(run())
    # To test your server:
    # - Browser:
    #   http://junk
    #   http://junk/table
    #   # test redirect back to /
    #   http://junk/redirect
    #
    # - Terminal:
    #   $ curl http://junk
    #   or
    #   $ curl http://junk/table
    #
    # - To test HTTP redirection:
    #   curl http://junk/redirect -v
