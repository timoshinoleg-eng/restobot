import json, subprocess, sys

result = subprocess.run(['terraform', 'providers', 'schema', '-json'], capture_output=True, text=True, cwd='/tmp/diag')
schema = json.loads(result.stdout)
container = schema["provider_schemas"]["registry.terraform.io/yandex-cloud/yandex"]["resource_schemas"]["yandex_serverless_container"]
connectivity = container["block"]["block_types"]["connectivity"]
print(json.dumps(connectivity, indent=2))
