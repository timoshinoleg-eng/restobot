import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# Try to get self subject info
req = urllib.request.Request(
    'https://iam.api.cloud.yandex.net/iam/v1/sessions/me',
    headers={'Authorization': f'Bearer {token}'}
)
try:
    resp = urllib.request.urlopen(req)
    print(resp.read().decode())
except Exception as e:
    print(f"Error: {e}")

# Also try iam token info
req2 = urllib.request.Request(
    'https://iam.api.cloud.yandex.net/iam/v1/tokens',
    headers={'Authorization': f'Bearer {token}'}
)
try:
    resp2 = urllib.request.urlopen(req2)
    print(resp2.read().decode())
except Exception as e:
    print(f"Error2: {e}")
