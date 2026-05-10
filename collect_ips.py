import json, urllib.request, time

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

CONTAINER_URL = "URL_PLACEHOLDER"

ips = set()
for i in range(5):
    try:
        req = urllib.request.Request(
            CONTAINER_URL,
            headers={'Authorization': f'Bearer {token}'}
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        ip = data.get('my_ip', 'unknown')
        ips.add(ip)
        print(f"Run {i+1}: my_ip={ip}")
    except Exception as e:
        print(f"Run {i+1}: error={e}")
    time.sleep(15)

print(f"\nUnique IPs ({len(ips)}): {sorted(ips)}")
