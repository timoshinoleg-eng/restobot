import socket

for name, host, port in [("postgres", "10.0.1.11", 6432), ("redis", "10.0.1.25", 6379)]:
    try:
        s = socket.create_connection((host, port), timeout=3)
        print(f"{name}: ok")
        s.close()
    except Exception as e:
        print(f"{name}: fail - {e}")
