import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# Check PostgreSQL config
req = urllib.request.Request(
    'https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/c9qo0pc0pk09v71olrte',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print("=== PostgreSQL ===")
print(f"assignPublicIp: {data.get('configSpec',{}).get('assignPublicIp', 'NOT_FOUND')}")
print(f"hosts publicIp: {[h.get('assignPublicIp', 'unknown') for h in data.get('hosts', [])]}")

# Check Redis config
req2 = urllib.request.Request(
    'https://mdb.api.cloud.yandex.net/managed-redis/v1/clusters/c9qsvhop6gd7c82rlmv6',
    headers={'Authorization': f'Bearer {token}'}
)
resp2 = urllib.request.urlopen(req2)
data2 = json.loads(resp2.read())
print("\n=== Redis ===")
print(f"assignPublicIp: {data2.get('configSpec',{}).get('assignPublicIp', 'NOT_FOUND')}")
print(f"hosts publicIp: {[h.get('assignPublicIp', 'unknown') for h in data2.get('hosts', [])]}")
