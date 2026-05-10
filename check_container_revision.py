import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

CONTAINER_ID = 'bbaqq30h9bmtuaabskhb'

req = urllib.request.Request(
    f'https://serverless-containers.api.cloud.yandex.net/containers/v1/containers/{CONTAINER_ID}',
    headers={'Authorization': f'Bearer {token}'}
)
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
