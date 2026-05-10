import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

for subnet_id in ['e9b228emg6g2iqkoi5b4', 'e2ls4u518tomjt0pqh4h', 'fl8nlcaes68n7gh9ameb']:
    req = urllib.request.Request(
        f'https://vpc.api.cloud.yandex.net/vpc/v1/subnets/{subnet_id}',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(f"Subnet {data['name']} ({subnet_id}): {data.get('v4CidrBlocks', [])}")
    print(f"  Used IPs: {data.get('usedIps', 'unknown')}")
