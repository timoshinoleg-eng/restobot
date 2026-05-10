import re

with open("/opt/restobot/infra/yc/containers.tf", "r") as f:
    lines = f.readlines()

connectivity_block = [
    "\n",
    "  connectivity {\n",
    "    network_id = yandex_vpc_network.restobot.id\n",
    "  }\n",
    "\n",
]

# Find image { lines for admin_api and public_api and insert connectivity before them
# admin_api image { is at line 19 -> index 18
# public_api image { is at line 107 -> index 106
insert_positions = [18, 106]

for pos in reversed(insert_positions):
    lines = lines[:pos] + connectivity_block + lines[pos:]

with open("/opt/restobot/infra/yc/containers.tf", "w") as f:
    f.writelines(lines)

print("connectivity blocks added")
