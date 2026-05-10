import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

req = urllib.request.Request(
    'https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/c9qo0pc0pk09v71olrte',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print("=== configSpec.access ===")
print(json.dumps(data.get('configSpec',{}).get('access',{}), indent=2))
print("\n=== Full configSpec keys ===")
print(list(data.get('configSpec',{}).keys()))
