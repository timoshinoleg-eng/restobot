import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# Try REST API for Cloud Logging
req = urllib.request.Request(
    'https://logging.api.cloud.yandex.net/log-reading/v1/read?folderId=b1g447hnv7s5o74n4qcr&since=2026-05-05T06:00:00Z&until=2026-05-05T10:00:00Z&pageSize=50',
    headers={'Authorization': f'Bearer {token}'}
)
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
except Exception as e:
    print(f"Error: {e}")
