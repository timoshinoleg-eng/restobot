import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

NETWORK_ID = 'enp9gvbk39vipha0ib4o'

# List route tables
req = urllib.request.Request(
    f'https://vpc.api.cloud.yandex.net/vpc/v1/routeTables?folderId=b1g447hnv7s5o74n4qcr',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print("=== Route Tables ===")
for rt in data.get('routeTables', []):
    if rt.get('networkId') == NETWORK_ID:
        print(f"RT: {rt['id']} {rt['name']}")
        for route in rt.get('staticRoutes', []):
            print(f"  {route}")

# List NAT gateways
req2 = urllib.request.Request(
    f'https://vpc.api.cloud.yandex.net/vpc/v1/gateways?folderId=b1g447hnv7s5o74n4qcr',
    headers={'Authorization': f'Bearer {token}'}
)
resp2 = urllib.request.urlopen(req2)
data2 = json.loads(resp2.read())
print("\n=== NAT Gateways ===")
for gw in data2.get('gateways', []):
    if gw.get('networkId') == NETWORK_ID:
        print(f"GW: {gw['id']} {gw['name']} type={gw.get('type', 'unknown')}")
