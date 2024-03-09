from sys import print_exception, exit
from os import stat
#from micropython import mem_info
from gc import enable, collect
import network
from ubinascii import hexlify
import json
from time import sleep
wlan = 'wlan{}'
SERVER_SSID = 'PicoW'  # max 32 characters
SERVER_SUBNET = '255.255.255.0'
WLAN_MODE = network.AP_IF  # network.STA_IF
PM_MAP = dict()
enable()  # gc


def file_exists(filename):
    try:
        stat(filename)
        return True
    except OSError:
        pass
    return False
    

class PropertiesFromFiles:

    def __init__(self, folder):
        self.folder = folder

    def __getattr__(self, item):
        file = '{}/{}.html'.format(self.folder, item.lower())
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
        return True
        #  This needs to be reworked. DB is different now...
        active_ids = self[base].setdefault('active', list())
        available_ids = self[base].setdefault('available', list(range(1, max + 1)))
        duplicate = list()
        integrity = True
        for k, v in self.items():
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
                    if dups:
                        integrity = False
                else:
                    integrity = False
            else:
                integrity = False
        for dup in duplicate:
            item = self.pop(dup)
            print('removing duplicate id {}: {} from db'.format(dup, item))
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
    _, best_channel = scan_wifi()
    ap = network.WLAN(network.AP_IF)

    ap.active(False)
    ssid = ssid or SERVER_SSID
    # make our hostname the same if not set
    network.hostname(hostname or ssid)
    ap.config(essid=ssid)
    ap.config(channel=best_channel)
    ap.config(pm=0xa11140)  # max power baby!
    if not password:
        ap.config(security=0)  # password=None
        password = 'no password'
    else:
        ap.config(password=password)
        ap.config(security=3)

    ap.active(True)
    while not ap.active():
        sleep(0.05)

    # reconfigure DHCP and DNS servers to OUR ip
    ip = list(ap.ifconfig())[0]
    ap.ifconfig((ip, SERVER_SUBNET, ip, ip))
    print('AP Mode Is Active, You can Now Connect {}, {}'.format(ssid, password))
    print('ifconfig: {}'.format(ap.ifconfig()))
    print('http://{}'.format(network.hostname()))
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
    wifi.config(ssid=ssid)
    wifi.config(pm=0xa11140)  # max power baby!
    if not password:
        wifi.config(security=0)
        password = None
    else:
        wifi.config(security=security)
        wifi.config(password=password)
    wifi.active(True)

    wifi.connect(ssid, password)
    while not wifi.isconnected():
        print('Waiting for connection...')
        sleep(1)
    ip = wifi.ifconfig()
    print('Connected to AP: {} our IP: {}'.format(ssid, ip))
    # ([(ip, subnet, gateway, dns)])  Presume the clacker IP IS the gateway (for now)
    return ip[0], ip[2]


def get_best_channel(ap_list):
    # https://en.wikipedia.org/wiki/List_of_WLAN_channels
    # find the wifi channel of 1, 6, 11 for which has the least RSSI competition
    overlap = {
        1: 1, 2: 1, 3: 1,
        4: 6, 5: 6, 6: 6, 7: 6, 8: 6,
        9: 11, 10: 11, 11: 11, 12: 11, 13: 11, 14: 11
    }
    hits = {1: 0.0, 6: 0.0, 11: 0.0}
    for ap in ap_list:
        if ap['RSSI'] < -80:
            # Very far away Neighbor's house
            hits[overlap[ap['channel']]] += .25
        elif ap['RSSI'] < -65:
            # Next Door Neighbor
            hits[overlap[ap['channel']]] += .5
        else:
            # Inside the house
            hits[overlap[ap['channel']]] += 1.0
    min_hits = min(hits.values())
    channel = [k for k, v in hits.items() if v == min_hits][0]
    print(hits, channel)
    return channel


def scan_wifi(match=None):
    wifi = network.WLAN(network.STA_IF)
    prev_active = wifi.active()
    wifi.active(True)
    collect()  # gc
    raw_aps = wifi.scan()
    wifi.active(prev_active)
    raw_aps.sort(key=lambda x: -x[3])  # sort by strongest signal strength
    ap_list = []
    for ap in raw_aps:
        (ssid, bssid, channel, RSSI, security, hidden) = ap
        ap_list.append({
            'ssid': ssid.decode('utf-8'),
            'bssid': hexlify(bssid).decode(),
            'channel': channel,
            'RSSI': RSSI,
            'security': security,
            'hidden': hidden
        })
        print(ap_list[-1])
    clearest_channel = get_best_channel(ap_list)
    if match:
        return [ap for ap in ap_list if all(m.lower() in ap['ssid'].lower() for m in match)], clearest_channel

    return ap_list, clearest_channel


def _handle_exception(_loop, context):
    """ uasyncio v3 only: global exception handler """
    print('Global exception handler')
    print_exception(context['exception'])
    exit()


def get_mac(sep=''):  # set sep=':' for a pretty mac
    mac = hexlify(network.WLAN().config('mac'), ':').decode()
    return sep.join(mac.split(':')).upper()


def mac_to_hostname(base=SERVER_SSID):
    wifi = network.WLAN(WLAN_MODE)
    wifi.active(True)
    network.hostname('{}_{}'.format(base, get_mac('')[-2:]))
    PM_MAP.update({
        wifi.PM_NONE: 'PM_NONE',
        wifi.PM_PERFORMANCE: 'PM_PERFORMANCE',
        wifi.PM_POWERSAVE: 'PM_POWERSAVE'})
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
                wifi_status[wlan.format(c)] = int(network.WLAN().config(c))
            elif c in ['pm']:
                v = network.WLAN().config(c)
                wifi_status[wlan.format(c)] = PM_MAP.get(v, v)
            elif c in ['mac']:
                wifi_status[wlan.format(c)] = hexlify(network.WLAN().config('mac'), ':').decode()
            else:
                wifi_status[wlan.format(c)] = network.WLAN().config(c)
        except Exception as e:
            wifi_status[wlan.format(c)] = 'UNKNOWN'
            print_exception(e)
    return wifi_status
