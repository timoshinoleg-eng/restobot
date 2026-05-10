import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

req = urllib.request.Request(
    'https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/c9qo0pc0pk09v71olrte',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print("=== securityGroupIds ===")
print(data.get('securityGroupIds', []))
print("\n=== host names ===")
for host in data.get('hosts', []):
    print(host.get('name'), host.get('zoneId'), host.get('subnetId'))
