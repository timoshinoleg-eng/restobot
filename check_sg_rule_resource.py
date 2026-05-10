import json, subprocess

result = subprocess.run(['terraform', 'providers', 'schema', '-json'], capture_output=True, text=True, cwd='/opt/restobot/infra/yc')
schema = json.loads(result.stdout)
resources = schema["provider_schemas"]["registry.terraform.io/yandex-cloud/yandex"]["resource_schemas"]
print("yandex_vpc_security_group_rule exists:", "yandex_vpc_security_group_rule" in resources)
print("yandex_vpc_security_group exists:", "yandex_vpc_security_group" in resources)
