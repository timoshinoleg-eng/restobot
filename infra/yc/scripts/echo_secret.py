"""Print a secret value from the environment for Terraform command-based Lockbox entries."""

from __future__ import annotations

import os
import sys


def main() -> None:
    value = os.environ.get("SECRET_VALUE")
    if value is None:
        raise SystemExit("SECRET_VALUE is not set")
    sys.stdout.write(value)


if __name__ == "__main__":
    main()
