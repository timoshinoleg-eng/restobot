import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# List Redis clusters in folder
req = urllib.request.Request(
    'https://mdb.api.cloud.yandex.net/managed-redis/v1/clusters?folderId=b1g447hnv7s5o74n4qcr',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
for c in data.get('clusters', []):
    print(f"ID: {c['id']}")
    print(f"Name: {c['name']}")
    print(f"Status: {c.get('status', 'UNKNOWN')}")
    print(f"Security groups: {c.get('securityGroupIds', [])}")
    print(f"Host: {c.get('host', '')}")
    print("---")
