import json, urllib.request

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# List network interfaces for this VM
# First, list compute instances to find the VM ID
req = urllib.request.Request(
    'https://compute.api.cloud.yandex.net/compute/v1/instances?folderId=b1g447hnv7s5o74n4qcr',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())

for inst in data.get('instances', []):
    if '51.250.91.143' in str(inst.get('networkInterfaces', [])):
        print(f"VM: {inst['id']} {inst['name']}")
        for ni in inst.get('networkInterfaces', []):
            print(f"  NI: {ni['index']} subnet={ni.get('subnetId')} sg={ni.get('securityGroupIds', [])}")
