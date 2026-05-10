import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

NETWORK_ID = 'enp9gvbk39vipha0ib4o'

# List subnets
req = urllib.request.Request(
    f'https://vpc.api.cloud.yandex.net/vpc/v1/subnets?folderId=b1g447hnv7s5o74n4qcr',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
for subnet in data.get('subnets', []):
    if subnet.get('networkId') == NETWORK_ID:
        print(f"Subnet: {subnet['id']} {subnet['name']} {subnet['zoneId']}")
        print(f"  CIDR: {subnet.get('v4CidrBlocks', [])}")
        print(f"  DHCP options: {subnet.get('dhcpOptions', {})}")
