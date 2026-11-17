"""Create the first platform admin. Development only, run by a person.

    set ALLOW_ADMIN_BOOTSTRAP=1        (PowerShell: $env:ALLOW_ADMIN_BOOTSTRAP="1")
    python scripts/bootstrap_admin.py you@example.com "Your Name"

The password is typed at a hidden prompt, never passed on the command line
(command lines end up in shell history and process lists).
Refuses when APP_ENV=production. See app/services/accounts.py.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.services.accounts import AccountError, create_platform_staff  # noqa: E402
from app.services.passwords import PasswordError  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    email, name = sys.argv[1], sys.argv[2]
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.")
        return 1
    db = SessionLocal()
    try:
        user = create_platform_staff(db, email=email, display_name=name, password=password)
    except (AccountError, PasswordError) as exc:
        print(f"Refused: {exc}")
        return 1
    finally:
        db.close()
    print(f"Created platform_admin {user.email} (id {user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
