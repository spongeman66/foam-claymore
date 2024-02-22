import network
import socket
import uasyncio as asyncio
from ubinascii import hexlify

SERVER_SSID = 'PicoW'  # max 32 characters
SERVER_SUBNET = '255.255.255.0'
WLAN_MODE = network.AP_IF  # network.STA_IF
PM_MAP = dict()

class PropertiesFromFiles:

    def __init__(self, folder):
        self.folder = folder

    def __getattr__(self, item):
        file = f"{self.folder}/{item.lower()}.html"
        print(f"{item.lower()} Reading from {file}")
        with open(file) as fh:
            setattr(self, item, str(fh.read()))
        return getattr(self, item)


def wifi_start_access_point(ssid=None, password=None, hostname=None):
    """ set up the access point """
    ap = network.WLAN(network.AP_IF)
    ssid = ssid or SERVER_SSID
    # make our hostname the same if not set
    network.hostname(hostname or ssid)
    if not password:
        ap.config(essid=ssid, security=0)
        password = 'OPEN'
    else:
        ap.config(essid=ssid, password=password, security=3)
    ap.active(True)
    while not ap.active():
        asyncio.sleep(0.05)

    # reconfigure DHCP and DNS servers to OUR ip
    ip = list(ap.ifconfig())[0]
    ips = (ip, SERVER_SUBNET, ip, ip)
    ap.ifconfig(ips)
    print(f'AP Mode Is Active, You can Now Connect {ssid}, "{password}"')
    print(f'ifconfig: {ap.ifconfig()}')
    print(f"http://{network.hostname()}")
    return ip


def _handle_exception(_loop, context):
    """ uasyncio v3 only: global exception handler """
    print('Global exception handler')
    sys.print_exception(context["exception"])
    sys.exit()


def mac_to_hostname(base=SERVER_SSID):
    wlan = network.WLAN(WLAN_MODE)
    active_state = wlan.active()
    print(f"{active_state=}")
    if not active_state:
        wlan.active(True)
        while not wlan.active():
            asyncio.sleep(0.05)
    print(f"{wlan.active()=}")
    mac2 = hexlify(wlan.config('mac')).decode()[-2:]
    network.hostname(f"{base}_{mac2}")
    # return to how we found it
    wlan.active(active_state)
    if not active_state:
        while wlan.active():
            asyncio.sleep(0.05)
    print(f"{wlan.active()=}")
    PM_MAP.update({
        wlan.PM_NONE: 'PM_NONE',
        wlan.PM_PERFORMANCE: 'PM_PERFORMANCE',
        wlan.PM_POWERSAVE: 'PM_POWERSAVE'})

    return network.hostname()


def get_wifi_status():
    wifi_status = {
        'wlanstatus': network.WLAN().status(),
        'wlanrssi': network.WLAN().status('rssi'),
        'wlanconnected': network.WLAN().isconnected()}
    for c in [
            'mac', 'ssid', 'channel', 'security',
            'hostname', 'txpower', 'pm']:
        try:
            if c in ['txpower']:
                wifi_status[f'wlan{c}'] = int(network.WLAN().config(c))
            elif c in ['pm']:
                v = network.WLAN().config(c)
                wifi_status[f'wlan{c}'] = PM_MAP.get(v, v)
            elif c in ['mac']:
                wifi_status[f'wlan{c}'] = hexlify(network.WLAN().config('mac'), ':').decode()
            else:
                wifi_status[f'wlan{c}'] = network.WLAN().config(c)
        except Exception as e:
            wifi_status[f'wlan{c}'] = 'UNKNOWN'
            sys.print_exception(e)
    return wifi_status


def print_wifi():
    print(get_wifi_status())
