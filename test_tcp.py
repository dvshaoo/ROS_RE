import socket
import sys
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect(('127.0.0.1', 25000))
    print('Connected to 127.0.0.1:25000!')
    s.send(b'hello')
    data = s.recv(1024)
    print('Received:', repr(data))
    s.close()
except Exception as e:
    print('Error:', str(e))
