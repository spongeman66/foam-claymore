"""
Minimal captive portal, using uasyncio v3
Intended for Raspberry Pi Pico W

* Author: Rod Slattery <rod.slattery@gmail.com>

Built upon:
- https://github.com/p-doyle/Micropython-DNSServer-Captive-Portal

References:
- http://docs.micropython.org/en/latest/library/uasyncio.html
- https://github.com/peterhinch/micropython-async/blob/master/v3/README.md
- https://github.com/peterhinch/micropython-async/blob/master/v3/docs/TUTORIAL.md
- https://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html#sec5
"""
import sys
import socket
import uasyncio as asyncio


class DNSQuery:
    def __init__(self, data):
        self.data = data
        domain = []
        tipo = (data[2] >> 3) & 15  # Opcode bits
        if tipo == 0:  # Standard query
            ini = 12
            lon = data[ini]
            while lon != 0:
                domain.append(data[ini + 1:ini + lon + 1].decode('utf-8') + '.')
                ini += lon + 1
                lon = data[ini]
        self.domain = ''.join(domain)

    def response(self, ip):
        if self.domain:
            packet = [
                self.data[:2] + b'\x81\x80',
                self.data[4:6] + self.data[4:6] + b'\x00\x00\x00\x00',  # Questions and Answers Counts
                self.data[12:],  # Original Domain Name Question
                b'\xC0\x0C',     # Pointer to domain name
                b'\x00\x01\x00\x01\x00\x00\x00\x3C\x00\x04',  # Response type, ttl and resource data length -> 4 bytes
                bytes(map(int, ip.split('.')))]  # 4bytes of IP
            return b''.join(packet)


class CaptivePortal:
    """
    Intended for standalone AP-Mode Wi-Fi projects
    IP address of the Pico W does not need to be known by the user
    because all dns queries are re-directed to the PicoW ip address
    Presumes an asyncio http server will also be running on port 80
    Expects:
    # wireless lan to be in AP mode
    ap = network.WLAN(network.AP_IF)
    # Both the DNS and DHCP server to be our own IP address
    ip = list(ap.ifconfig())[0]
    ips = (ip, SERVER_SUBNET, ip, ip)
    ap.ifconfig(ips)

    """
    def __init__(self, server_ip):
        """
        return server_ip (our IP) for any dns request
        this will direct all initial traffic to:
        http://{our ip address}/
        """
        self.server_ip = server_ip

    async def run_dns_server(self):
        """ create udp server for dns queries and respond forever """
        udps = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udps.setblocking(False)
        udps.bind(('0.0.0.0', 53))

        while True:
            try:
                # gc.collect()
                yield asyncio.core._io_queue.queue_read(udps)
                data, addr = udps.recvfrom(4096)
                dns = DNSQuery(data)
                udps.sendto(dns.response(self.server_ip), addr)

            except Exception as e:
                sys.print_exception(e)
                await asyncio.sleep_ms(3000)

    async def add_server(self, loop=None):
        """
        Adds this server to the asyncio loop specified or the default event loop
        :param loop: asyncio loop that will service this server
        :return: the event loop
        After adding this server, be sure to loop.run_forever()
        """
        loop = loop or asyncio.get_event_loop()
        loop.create_task(self.run_dns_server())
        return loop
