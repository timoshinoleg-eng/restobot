import urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

req = urllib.request.Request(
    'https://bbaqq30h9bmtuaabskhb.containers.yandexcloud.net/',
    headers={'Authorization': f'Bearer {token}'}
)
try:
    resp = urllib.request.urlopen(req)
    print(resp.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code}")
    print(e.read().decode())
except Exception as e:
    print(f"Error: {e}")
