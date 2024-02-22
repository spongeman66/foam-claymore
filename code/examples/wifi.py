import socket
import network
from time import sleep
from picozero import pico_temp_sensor, pico_led



ssid = 'spongeNET'
password = 'RodShawnyaRileyWalkerSlattery'


def connect():
    # Connect to WLAN
    hostname = network.hostname()
    print(f"HOSTNAME: {hostname}")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        print('Waiting for connection...')
        sleep(1)
    ip = wlan.ifconfig()
    print(f"Connected on {ip}")
    return ip[0]


def open_socket(ip):
    # Open a socket
    address = (ip, 80)
    connection = socket.socket()
    connection.bind(address)
    connection.listen(5)  # max 5 connections
    return connection


def webpage(temperature, state, servo_pos):
    # Template HTML
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
        <p>Servo Position: {servo_pos}</p>
        <p>LED is {state}</p>
        <p>Temperature is {temperature}</p>
        </font>
        </body>
        </html>
        """
    return str(html)


def serve(connection):
    # Start a web server
    state = 'OFF'
    pico_led.off()
    temperature = 0
    servo_pos = ServoMin
    while True:
        client = connection.accept()[0]
        request = client.recv(1024)
        request = str(request)

        print(request)
        try:
            request = request.split()[1]
        except IndexError:
            pass
        if request == '/lighton?':
            pico_led.on()
            state = 'ON'
            servo_pos = ServoMax
        #            for pos in range(1000, ServoMax, 50):
        #                setServoPosition(pos)
        elif request == '/lightoff?':
            pico_led.off()
            servo_pos = ServoMin
            state = 'OFF'
        #            for pos in range(ServoMax, 1000, -50):
        #                setServoPosition(pos)
        servo_pos = setServoPosition(servo_pos)
        temperature = pico_temp_sensor.temp
        html = webpage(temperature, state, servo_pos)
        client.send(html)
        client.close()
