import argparse
import asyncio
import sys
from sqlalchemy.orm import Session
from db import SessionLocal, engine, Base
from models import Monitor, CheckResult
from checker import run_checks

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        pass

async def list_monitors():
    db = get_db()
    monitors = db.query(Monitor).all()
    print(f"{'ID':<5} {'Name':<20} {'URL':<40} {'Status':<10}")
    print("-" * 80)
    for m in monitors:
        last_check = db.query(CheckResult).filter(CheckResult.monitor_id == m.id).order_by(CheckResult.checked_at.desc()).first()
        status = "N/A"
        if last_check:
            status = "UP" if last_check.is_up else "DOWN"
        
        active_str = "Active" if m.is_active else "Inactive"
        print(f"{m.id:<5} {m.name[:20]:<20} {m.url[:40]:<40} {status:<10} ({active_str})")
    db.close()

async def run_once_cmd():
    db = get_db()
    print("Running checks for all active monitors...")
    n = await run_checks(db)
    print(f"Done. Checked {n} monitors.")
    db.close()

async def add_monitor(name: str, url: str):
    db = get_db()
    m = Monitor(name=name, url=url, interval_seconds=60, is_active=True)
    db.add(m)
    db.commit()
    print(f"Added monitor: {name} ({url})")
    db.close()

def main():
    parser = argparse.ArgumentParser(description="Web Health Monitor CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List
    subparsers.add_parser("list", help="List all monitors")

    # Run-once
    subparsers.add_parser("run-once", help="Run checks once manually")

    # Add
    add_parser = subparsers.add_parser("add", help="Add a new monitor")
    add_parser.add_argument("name", help="Name of the monitor")
    add_parser.add_argument("url", help="URL to monitor")

    args = parser.parse_args()

    if args.command == "list":
        asyncio.run(list_monitors())
    elif args.command == "run-once":
        asyncio.run(run_once_cmd())
    elif args.command == "add":
        asyncio.run(add_monitor(args.name, args.url))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
