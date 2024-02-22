"""
Minimal captive portal example, using uasyncio v3
Intended for Raspberry Pi Pico W

* Author: Rod Slattery <rod.slattery@gmail.com>
"""
import uasyncio as asyncio
from helpers import wifi_start_access_point, _handle_exception
from captive_portal import CaptivePortal
from examples.hello_world_server import MyApp


if __name__ == '__main__':
    async def start_both():
        print("starting AP")
        our_ip = wifi_start_access_point()
        
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

    try:
        asyncio.run(start_both())
    except KeyboardInterrupt:
        print('Bye')
    finally:
        asyncio.new_event_loop()  # Clear retained state
    print("DONE")
