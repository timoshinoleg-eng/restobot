import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# Check PostgreSQL cluster network
req = urllib.request.Request(
    'https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/c9qo0pc0pk09v71olrte',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print("=== PostgreSQL network ===")
print(f"networkId: {data.get('networkId', 'NONE')}")
print(f"securityGroupIds: {data.get('securityGroupIds', [])}")

# Check Redis cluster network
req2 = urllib.request.Request(
    'https://mdb.api.cloud.yandex.net/managed-redis/v1/clusters/c9qsvhop6gd7c82rlmv6',
    headers={'Authorization': f'Bearer {token}'}
)
resp2 = urllib.request.urlopen(req2)
data2 = json.loads(resp2.read())
print("\n=== Redis network ===")
print(f"networkId: {data2.get('networkId', 'NONE')}")
print(f"securityGroupIds: {data2.get('securityGroupIds', [])}")
