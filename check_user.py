import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# List clouds to see what this token can access
req = urllib.request.Request(
    'https://resource-manager.api.cloud.yandex.net/resource-manager/v1/clouds',
    headers={'Authorization': f'Bearer {token}'}
)
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print("Clouds:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error listing clouds: {e}")

# Also try to get folder access bindings
req2 = urllib.request.Request(
    'https://resource-manager.api.cloud.yandex.net/resource-manager/v1/folders/b1g447hnv7s5o74n4qcr:ListAccessBindings',
    headers={'Authorization': f'Bearer {token}'}
)
try:
    resp2 = urllib.request.urlopen(req2)
    data2 = json.loads(resp2.read())
    print("\nFolder bindings:")
    print(json.dumps(data2, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error listing bindings: {e}")
