import socket
import os

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('localhost', int(port))) == 0

ports = [
    ("MLflow", 5000),
    ("ArgoCD", 8080),
    ("Web UI", 8501)
]

print("--- KyberTune Status Check ---")
for name, port in ports:
    status = "OK" if check_port(port) else "DOWN"
    print(f"{name} ({port}): {status}")
