import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# List cloud access bindings
req = urllib.request.Request(
    'https://resource-manager.api.cloud.yandex.net/resource-manager/v1/clouds/b1gjpgljv362fficoq13:listAccessBindings',
    headers={'Authorization': f'Bearer {token}'}
)
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")

# Also try folder access bindings with POST
req2 = urllib.request.Request(
    'https://resource-manager.api.cloud.yandex.net/resource-manager/v1/folders/b1g447hnv7s5o74n4qcr:listAccessBindings',
    headers={'Authorization': f'Bearer {token}'},
    data=b''
)
try:
    resp2 = urllib.request.urlopen(req2)
    data2 = json.loads(resp2.read())
    print("\nFolder bindings:")
    print(json.dumps(data2, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error2: {e}")
