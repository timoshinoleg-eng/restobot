import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

req = urllib.request.Request(
    'https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters?folderId=b1g447hnv7s5o74n4qcr',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
for c in data.get('clusters', []):
    print(c['id'], c['name'], c['status'])
