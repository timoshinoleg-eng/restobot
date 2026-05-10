import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

req = urllib.request.Request(
    'https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/c9qo0pc0pk09v71olrte/hosts',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print(json.dumps(data, indent=2, ensure_ascii=False))
