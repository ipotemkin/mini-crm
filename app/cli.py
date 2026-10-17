"""CLI: hash-password, gen-key, backup, seed-demo, google-auth."""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import date, timedelta
from decimal import Decimal

from cryptography.fernet import Fernet


def cmd_hash_password(_: argparse.Namespace) -> None:
    from app.core.security import hash_password

    password = getpass.getpass("Password: ")
    print(hash_password(password))


def cmd_gen_key(_: argparse.Namespace) -> None:
    print(Fernet.generate_key().decode())


def cmd_backup(_: argparse.Namespace) -> None:
    from app.jobs.backup import run_backup

    path = run_backup()
    print(path or "No database to backup")


def cmd_seed(_: argparse.Namespace) -> None:
    from app import db as dbmod
    from app.schemas.client import ClientCreate
    from app.schemas.deal import DealCreate
    from app.schemas.order import OrderCreate
    from app.schemas.task import TaskCreate
    from app.core.enums import (
        ClientStatus,
        ClientType,
        DealStatus,
        TaskType,
    )
    from app.services import clients, deals, orders, tasks

    dbmod.get_engine()
    assert dbmod.SessionLocal is not None
    db = dbmod.SessionLocal()
    try:
        c1 = clients.create_client(
            db,
            ClientCreate(
                name="ООО Ромашка",
                contact_person="Иванов Иван",
                phone="+7 (999) 123-45-67",
                email="info@romashka.example",
                status=ClientStatus.ACTIVE,
                source="Сайт",
            ),
        )
        c2 = clients.create_client(
            db,
            ClientCreate(
                name="Петров Пётр",
                client_type=ClientType.PERSON,
                phone="89997654321",
                email="petrov@example.com",
                status=ClientStatus.LEAD,
            ),
        )
        d1 = deals.create_deal(
            db,
            DealCreate(
                title="Поставка оборудования",
                client_id=c1.id,
                amount=Decimal("150000.00"),
                status=DealStatus.IN_PROGRESS,
            ),
        )
        deals.create_deal(
            db,
            DealCreate(
                title="Консультация",
                client_id=c2.id,
                amount=Decimal("25000.00"),
            ),
        )
        orders.create_order(
            db,
            OrderCreate(
                title="Партия №1",
                deal_id=d1.id,
                client_id=c1.id,
                amount=Decimal("75000.00"),
            ),
        )
        tasks.create_task(
            db,
            TaskCreate(
                title="Позвонить по счёту",
                task_type=TaskType.CALL,
                client_id=c1.id,
                deal_id=d1.id,
                due_date=date.today(),
            ),
        )
        tasks.create_task(
            db,
            TaskCreate(
                title="Подготовить КП",
                client_id=c2.id,
                due_date=date.today() + timedelta(days=2),
            ),
        )
        print("Demo data created")
    finally:
        db.close()


def cmd_google_auth(_: argparse.Namespace) -> None:
    print(
        "CLI google-auth: используйте Desktop OAuth client "
        "(GOOGLE_OAUTH_CLIENT_FILE) и ssh -L 8765:127.0.0.1:8765.\n"
        "Для MVP предпочтителен UI-поток: /settings → Подключить Google."
    )
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("hash-password")
    p.set_defaults(func=cmd_hash_password)

    p = sub.add_parser("gen-key")
    p.set_defaults(func=cmd_gen_key)

    p = sub.add_parser("backup")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("seed-demo")
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("google-auth")
    p.set_defaults(func=cmd_google_auth)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
