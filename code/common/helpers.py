import sys
import os
from micropython import mem_info
import gc
gc.enable()
import network
# import socket
import uasyncio as asyncio
from ubinascii import hexlify
import json

SERVER_SSID = 'PicoW'  # max 32 characters
SERVER_SUBNET = '255.255.255.0'
WLAN_MODE = network.AP_IF  # network.STA_IF
PM_MAP = dict()


def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        pass
    return False
    

class PropertiesFromFiles:

    def __init__(self, folder):
        self.folder = folder

    def __getattr__(self, item):
        file = f"{self.folder}/{item.lower()}.html"
        print(f"{item.lower()} Reading from {file}")
        with open(file) as fh:
            setattr(self, item, str(fh.read()))
        return getattr(self, item)


class Database(dict):
    def __init__(self, filename, *args):
        self.__filename = filename
        d = self.init_from_file()
        super().__init__(list(args) + list(d.items()))

    def init_from_file(self):
        if file_exists(self.__filename):
            with open(self.__filename, 'rb') as fh:
                return json.load(fh)
        return {}

    def flush(self):
        with open(self.__filename, 'wb') as fh:
            fh.write(json.dumps(self))

    def verify_integrity(self, base='clacker', id='id', max=4):
        active_ids = self[base].setdefault('active', list())
        available_ids = self[base].setdefault('available', list(range(1, max + 1)))
        duplicate = list()
        print('Checking DB integrity')
        for k, v in self.items():
            print(k, v)
            if k == base:
                continue
            if id in v:
                if int(v[id]) in available_ids:
                    available_ids.remove(int(v[id]))
                    active_ids.append(int(v[id]))
                elif int(v[id]) in active_ids:
                    dups = [
                        k2 for k2, v2 in self.items()
                        if int(v2.get(id, -1)) == v[id]]
                    print(f'DB error duplicate {id}s: {v[id]}: {dups}')
                    duplicate.extend(dups)
                else:
                    print(f'unknown ID: {v[id]}')
                    print(self)
            else:
                print(f'db item did not have an {id}!')
        for dup in duplicate:
            item = self.pop(dup)
            print(f"removing duplicate id {dup}: {item} from db")
            if int(item[id]) in active_ids:
                active_ids.remove(int(item[id]))
            if int(item[id]) not in available_ids:
                available_ids.remove(int(item[id]))
        available_ids.sort()
        active_ids.sort()
        self[base]['available'] = available_ids
        self[base]['active'] = active_ids


def wifi_start_access_point(ssid=None, password=None, hostname=None):
    """ set up the access point """
    ap_list, best_channel = scan_wifi()
    print('found aps:', ap_list)
    ap = network.WLAN(network.AP_IF)
    print(f'{best_channel=} {ap.active()=}')
    ap.active(False)

    ssid = ssid or SERVER_SSID
    # make our hostname the same if not set
    network.hostname(hostname or ssid)
    if not password:
        configs = {'essid': ssid, 'security': 0, 'channel': best_channel}
        # ap.config(essid=ssid, security=0, channel=best_channel)
        password = 'OPEN'
        for k, v in configs.items():
            ap.config(**{k: v})
    else:
        ap.config(essid=ssid, password=password, security=3, channel=best_channel)


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


def wifi_connect_to_access_point(ssid, password=None, security=0):
    """
    Parameters:
    ssid[str]: The name of the ap you want to connect
    password[str]: Password for your internet connection
    hostname[str]: hostname for this device
    Returns: Your ip address
    """
    # Just making our internet connection
    wifi = network.WLAN(network.STA_IF)
    if not password:
        wifi.config(ssid=ssid, security=0)
        password = None
    else:
        wifi.config(essid=ssid, security=security)
    wifi.active(True)

    wifi.connect(ssid, password)
    while not wifi.isconnected():
        print('Waiting for connection...')
        asyncio.sleep(1)
    ip = wifi.ifconfig()
    print(f"Connected to AP: {ssid} our IP: {ip}")
    # ([(ip, subnet, gateway, dns)])  Presume the clacker IP IS the gateway (for now)
    return ip[0], ip[2]

def best_channel(ap_list):
    # https://en.wikipedia.org/wiki/List_of_WLAN_channels
    # find the wifi channel of 1, 6, 11 for which has the least RSSI competition
    overlap = {
        1: 1, 2: 1, 3: 1,
        4: 6, 5: 6, 6: 6, 7: 6, 8: 6,
        9: 11, 10: 11, 11: 11, 12: 11, 13: 11, 14: 11
    }
    hits = {1: 0.0, 6: 0.0, 11: 0.0}
    print(f'checking: {len(ap_list)}')
    for ap in ap_list:
        strength = 1.0
        if ap['RSSI'] < -80:
            strength = .25
        elif ap['RSSI'] < -65:
            strength = .5

        hits[overlap[ap['channel']]] += strength
    min_hits = min(hits.values())
    channel = [k for k, v in hits.items() if v == min_hits][0]
    print(hits, channel)

    return channel

def scan_wifi(match=None):
    print("m1\n", mem_info(), f"{gc.mem_free()=}")
    wifi = network.WLAN(network.STA_IF)
    prev_active = wifi.active()
    wifi.active(True)
    gc.collect()
    print("m2\n", mem_info(), f"{gc.mem_free()=}")
    while not wifi.active():
        asyncio.sleep_ms(50)
    gc.collect()
    print("m3\n", mem_info(), f"{gc.mem_free()=}")
    raw_aps = wifi.scan()
    raw_aps.sort(key=lambda x: -x[3])  # sort by strongest signal strength
    ap_list = []
    for ap in raw_aps:
        (ssid, bssid, channel, RSSI, security, hidden) = ap
        ap_list.append({
            'ssid': ssid.decode("utf-8"),
            'bssid': hexlify(bssid).decode(),
            'channel': channel,
            'RSSI': RSSI,
            'security': security,
            'hidden': hidden
        })
        print(ap_list[-1])
    clearest_channel = best_channel(ap_list)
    if match:
        return [ap for ap in ap_list if all(m.lower() in ap['ssid'].lower() for m in match)], clearest_channel

    wifi.active(prev_active)
    return ap_list, clearest_channel


def _handle_exception(_loop, context):
    """ uasyncio v3 only: global exception handler """
    print('Global exception handler')
    sys.print_exception(context["exception"])
    sys.exit()


def get_mac(sep=''):  # set sep=':' for a pretty mac
    mac = hexlify(network.WLAN().config('mac'), ':').decode()
    return sep.join(mac.split(':')).upper()


def mac_to_hostname(base=SERVER_SSID):
    wlan = network.WLAN(WLAN_MODE)
    wlan.active(True)
    # while not wlan.active():
    #     asyncio.sleep(0.05)
    print(f"{wlan.active()=}")
    network.hostname(f"{base}_{get_mac('')[-2:]}")
    # return to how we found it
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
