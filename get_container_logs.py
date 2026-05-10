import json, urllib.request
from datetime import datetime, timedelta, timezone

with open('/tmp/yc_token.txt') as f:
    token = f.read().strip()

# Get logs from the last 30 minutes
now = datetime.now(timezone.utc)
since = (now - timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')

req = urllib.request.Request(
    f'https://logging.api.cloud.yandex.net/log-reading/v1/read?folderId=b1g447hnv7s5o74n4qcr&since={since}&pageSize=50',
    headers={'Authorization': f'Bearer {token}'}
)
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    entries = data.get('entries', [])
    print(f"Found {len(entries)} log entries")
    for entry in entries:
        msg = entry.get('message', '')
        level = entry.get('level', 'UNKNOWN')
        ts = entry.get('timestamp', '')
        if 'health' in msg.lower() or 'error' in msg.lower() or 'database' in msg.lower() or 'redis' in msg.lower():
            print(f"[{ts}] {level}: {msg[:500]}")
except Exception as e:
    print(f"Error: {e}")
