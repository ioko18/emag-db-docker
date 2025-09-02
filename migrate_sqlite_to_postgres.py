# migrate_sqlite_to_postgres.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.product import Product
from sqlalchemy.exc import IntegrityError

load_dotenv()

SQLITE_URL = "sqlite:///./app.db"
POSTGRES_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://appuser:appsecret@127.0.0.1:5434/appdb"
)

# Engines & sesiuni separate
sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
pg_engine = create_engine(POSTGRES_URL)

SrcSession = sessionmaker(bind=sqlite_engine, autoflush=False, autocommit=False)
DstSession = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)

def main():
    src = SrcSession()
    dst = DstSession()

    # asigură-te că tabela există în PG (create_all e deja în app la startup,
    # dar lăsăm și aici pentru siguranță)
    Product.metadata.create_all(bind=pg_engine)  # type: ignore[attr-defined]

    rows = src.query(Product).all()
    print(f"Found {len(rows)} products in SQLite.")
    migrated = 0

    for r in rows:
        # creăm un nou obiect pentru destinație (evităm binding cross-session)
        copy = Product(id=r.id, name=r.name, description=r.description, price=r.price)
        try:
            dst.merge(copy)  # inseră sau upsertează după PK
            migrated += 1
        except IntegrityError:
            dst.rollback()
        except Exception as e:
            dst.rollback()
            print("Error on row:", r.id, e)

    dst.commit()
    src.close()
    dst.close()
    print(f"Migrated {migrated} rows.")

if __name__ == "__main__":
    main()
