#!/bin/bash
TOKEN="$(cat /tmp/yc_token.txt)"
CLUSTER_ID="c9qqlsuef9nuf0ff5nqe"
echo "=== GET cluster access config ==="
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/$CLUSTER_ID" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('configSpec',{}).get('access',{}), indent=2))"
