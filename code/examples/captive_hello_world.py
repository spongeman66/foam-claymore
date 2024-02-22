"""
Minimal captive portal, using uasyncio v3 (MicroPython 1.13+) with a fallback for earlier versions of uasyncio/MicroPython.

* License: MIT
* Repository: https://github.com/metachris/micropython-captiveportal
* Author: Chris Hager <chris@linuxuser.at> / https://twitter.com/metachris

Built upon:
- https://github.com/p-doyle/Micropython-DNSServer-Captive-Portal

References:
- http://docs.micropython.org/en/latest/library/uasyncio.html
- https://github.com/peterhinch/micropython-async/blob/master/v3/README.md
- https://github.com/peterhinch/micropython-async/blob/master/v3/docs/TUTORIAL.md
- https://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html#sec5
"""
import uasyncio as asyncio
from helpers import (wifi_start_access_point, _handle_exception, mac_to_hostname)
from captive_portal import CaptivePortal

from hello_world_server import MyApp

# Access point settings
SERVER_SSID = 'PicoW'  # max 32 characters


async def start_both():
    print("starting AP")
    our_ip = wifi_start_access_point(ssid=SERVER_SSID, password=None)

    print("Instantiate app")
    myapp = MyApp()
    print("Instantiate DNS")
    captive = CaptivePortal(our_ip)

    # Get the event loop
    loop = asyncio.get_event_loop()
    # Add global exception handler
    loop.set_exception_handler(_handle_exception)

    # Start the DNS server task
    await captive.add_server(loop)
    await myapp.add_server(loop)
    print('Looping forever...')
    loop.run_forever()


if __name__ == '__main__':
    try:
        asyncio.run(start_both())
    except KeyboardInterrupt:
        print('Bye')
    finally:
        asyncio.new_event_loop()  # Clear retained state
    print("DONE")
