import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

SG_ID = 'enpalmp64msgpupnbh75'

req = urllib.request.Request(
    f'https://vpc.api.cloud.yandex.net/vpc/v1/securityGroups/{SG_ID}',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
print("=== Security Group Rules ===")
for rule in data.get('rules', []):
    print(json.dumps(rule, indent=2, ensure_ascii=False))
