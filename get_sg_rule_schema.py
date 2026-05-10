import json, subprocess

result = subprocess.run(['terraform', 'providers', 'schema', '-json'], capture_output=True, text=True, cwd='/opt/restobot/infra/yc')
schema = json.loads(result.stdout)
rule = schema["provider_schemas"]["registry.terraform.io/yandex-cloud/yandex"]["resource_schemas"]["yandex_vpc_security_group_rule"]
print(json.dumps(rule, indent=2))
