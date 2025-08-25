import argparse
import os
from app import create_app
from app.extensions import db
from app.models import User
from app.config import Config


def init_db():
    app = create_app()
    with app.app_context():
        db.create_all()
        print("DB Tabellen erstellt")


def seed():
    app = create_app()
    with app.app_context():
        # Admin User V1 (alle Admin) – nur anlegen falls nicht vorhanden
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@example.com")
            db.session.add(admin)
            db.session.commit()
            print("Admin User angelegt")
        else:
            print("Admin User existiert bereits")


def main():
    parser = argparse.ArgumentParser(description="Orquestrix Management")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init-db", help="Erstellt DB Tabellen (create_all)")
    sub.add_parser("seed", help="Seed Daten (Admin User)")
    sub.add_parser("show-db", help="Zeigt verwendete DB Datei & Tabellenliste")

    args = parser.parse_args()

    if args.command == "init-db":
        init_db()
    elif args.command == "seed":
        seed()
    elif args.command == "show-db":
        app = create_app()
        with app.app_context():
            from sqlalchemy import text
            print("DB URI:", app.config["SQLALCHEMY_DATABASE_URI"])
            print("Physische Datei:", Config.DB_FILE, "Exists:", os.path.exists(Config.DB_FILE))
            res = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
            print("Tabellen:", [r[0] for r in res])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
