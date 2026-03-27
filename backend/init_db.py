from app.database import Base, engine, SessionLocal
from app.seed import seed_default_users


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_default_users(db)
    finally:
        db.close()
    print("Database siap. Tabel dibuat dan user default sudah di-seed.")


if __name__ == "__main__":
    main()
