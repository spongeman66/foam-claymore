import network
import time
import socket
from picozero import pico_temp_sensor, pico_led

class led_manager:
    states = ['OFF', 'ON']
    def __init__(self):
        self.set_state('OFF')
    def set_state(self, new_state):
        print(f'new_state={new_state}')
        if new_state in self.states:
            self.state = new_state
            print('current status:', pico_led.value)
            if self.states.index(new_state) != pico_led.value:
                pico_led.toggle()
    def get_state(self):
        return self.states[pico_led.value]
            


state = 'OFF'
pico_led.off()


def web_page():
  html = """<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
            <body><h1>Hello World</h1></body></html>
         """
  return html

def webpage(request, led):
    print(request)
    try:
        req = str(request).split()[1]
    except IndexError:
        pass
    print(req)
    if req == '/lighton?':
        led.set_state('ON')
    elif req =='/lightoff?':
        led.set_state('OFF')
    state = led.get_state()
    temperature = pico_temp_sensor.temp

    #Template HTML
    html = f"""
        <!DOCTYPE html>
        <html>
        <form action="./lighton">
        <input type="submit" value="Light on"  style="font-size : 150px; width: 100%; height: 200px;"  />
        </form>
        <form action="./lightoff">
        <input type="submit" value="Light off" style="font-size : 150px; width: 100%; height: 200px;"  />
        </form>
        <font size="7">
        <p>LED is {state}</p>
        <p>Temperature is {temperature}</p>
        </font>
        </body>
        </html>
        """
    return str(html)


# if you do not see the network you may have to power cycle
# unplug your pico w for 10 seconds and plug it in again
def ap_mode(ssid, password=None):
    """
        Description: This is a function to activate AP mode

        Parameters:

        ssid[str]: The name of your internet connection
        password[str]: Password for your internet connection

        Returns: Nada
    """
    hostname = network.hostname(ssid)  # set our hosname to the same as the AP to make it easy to find the web page

    # Just making our internet connection
    ap = network.WLAN(network.AP_IF)
    #ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '0.0.0.0'))
    if not password:
        ap.config(essid=ssid, security=0)
        print(f'AP Mode Is Active, You can Now Connect {ssid}, "OPEN"')
    else:
        ap.config(essid=ssid, password=password)
        print(f'AP Mode Is Active, You can Now Connect {ssid}, "{password}"')
    ap.active(True)

    while ap.active() == False:
        pass
    ifconfig = ap.ifconfig()
    print('IP Address To Connect to:: ' + ifconfig[0])
    print(f'ifconfig:: {ifconfig}')

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   #creating socket object
    s.bind(('', 80))
    s.listen(5)
    led = led_manager()
    while True:
      conn, addr = s.accept()
      print('Got a connection from %s' % str(addr))
      request = conn.recv(1024)
      # print('Content = %s' % str(request))
      #response = web_page()
      response = webpage(request, led)
      conn.send(response)
      conn.close()

#ap_mode('CLAYMORE-27', 'gooniesIsPassword')
ap_mode('claymore_27')  # open network for now
