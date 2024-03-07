"""
Simple asyncio server that serves static index.html
"""
import gc
import uasyncio as asyncio


class MyApp:

    async def add_server(self, loop):
        server = asyncio.start_server(self.handle_http_connection, "0.0.0.0", 80)
        loop.create_task(server)

    async def handle_http_connection(self, reader, writer):
        gc.collect()

        # Get HTTP request line
        data = await reader.readline()
        request_line = data.decode()
        addr = writer.get_extra_info('peername')
        print(f'Received {request_line.strip()} from {addr}')

        # Read headers, to make client happy (else curl prints an error)
        while True:
            gc.collect()
            line = await reader.readline()
            if line == b'\r\n': break

        # Handle the request
        if len(request_line) > 0:
            with open('index.html') as f:
                body = f.read()
            await writer.awrite('HTTP/1.0 200 OK\r\n\r\n' + body)

        # Close the socket
        await writer.aclose()


if __name__ == '__main__':
    # Main claymore entrypoint Only executed if this file is run, not imported
    from helpers import wifi_start_access_point, _handle_exception

    async def start_server():
        print("starting AP")
        our_ip = wifi_start_access_point()
        
        print("Instantiate app")
        myapp = MyApp()

        # Get the event loop
        loop = asyncio.get_event_loop()
        # Add global exception handler
        loop.set_exception_handler(_handle_exception)

        await myapp.add_server(loop)
        print('Looping forever...')
        loop.run_forever()

    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        print('Bye')
    finally:
        asyncio.new_event_loop()  # Clear retained state
    print("DONE")
