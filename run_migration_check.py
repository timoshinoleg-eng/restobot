import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

REVISION_ID = 'bbakds6gelau5v6smhkv'

# Try to execute the task container
req = urllib.request.Request(
    f'https://serverless-containers.api.cloud.yandex.net/containers/v1/revisions/{REVISION_ID}:execute',
    method='POST',
    headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    },
    data=json.dumps({}).encode()
)
try:
    resp = urllib.request.urlopen(req)
    print("Success:", resp.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTPError {e.code}:")
    print(e.read().decode())
except Exception as e:
    print(f"Error: {e}")
