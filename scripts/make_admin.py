import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal
from app.models.user import User


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/make_admin.py <email>")
        sys.exit(1)

    email = sys.argv[1]
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"[ERROR] No user found with email={email}")
            sys.exit(1)
        user.is_admin = True
        db.commit()
        print(f"[OK] {email} (id={user.id}) is now an admin.")
    finally:
        db.close()


if __name__ == "__main__":
    main()