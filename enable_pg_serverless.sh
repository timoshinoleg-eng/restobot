#!/bin/bash
set -e
TOKEN="$(cat /tmp/yc_token.txt)"
CLUSTER_ID="c9qo0pc0pk09v71olrte"

echo "=== PATCH serverless=true ==="
RESPONSE=$(curl -s -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"configSpec": {"access": {"serverless": true}}, "updateMask": "configSpec.access.serverless"}' \
  "https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/$CLUSTER_ID")

echo "PATCH response: $RESPONSE"
OP_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")
if [ -z "$OP_ID" ]; then
    echo "ERROR: no operation id returned"
    exit 1
fi
echo "Operation ID: $OP_ID"

echo "=== Waiting for operation to complete ==="
for i in {1..60}; do
    OP_JSON=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "https://operation.api.cloud.yandex.net/operations/$OP_ID")
    DONE=$(echo "$OP_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('done','false'))")
    STATUS=$(echo "$OP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',{}).get('status','UNKNOWN'))")
    echo "Check $i: done=$DONE status=$STATUS"
    if [ "$DONE" = "True" ]; then
        echo "Operation complete. Cluster status: $STATUS"
        break
    fi
    sleep 10
done

echo "=== Waiting for cluster to be RUNNING ==="
for i in {1..60}; do
    CLUSTER_STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" \
        "https://mdb.api.cloud.yandex.net/managed-postgresql/v1/clusters/$CLUSTER_ID" | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('status','UNKNOWN'))")
    echo "Cluster check $i: status=$CLUSTER_STATUS"
    if [ "$CLUSTER_STATUS" = "RUNNING" ]; then
        echo "Cluster is RUNNING"
        break
    fi
    sleep 10
done

echo "=== Done ==="
