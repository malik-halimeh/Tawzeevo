"""Scheduled jobs and master-key rotation (PHASE_04.md L; D-049, D-051, D-056, D-057, D-079).

    python -m tawzeevo_api.cli.backup_jobs run-due
    python -m tawzeevo_api.cli.backup_jobs rollup-views
    python -m tawzeevo_api.cli.backup_jobs run-reminders
    python -m tawzeevo_api.cli.backup_jobs rotate-master-key --new-kek-id kek-prod-2

The in-process scheduler (BACKUP_SCHEDULER_ENABLED=true, services/jobs.py) runs the first three
on its own; a hosting scheduler may call them here instead. Keys are read from the environment
only, never from arguments.
"""

from __future__ import annotations

import argparse
import os
import sys

from tawzeevo_api.config import get_settings
from tawzeevo_api.database import SessionLocal
from tawzeevo_api.errors import AppError
from tawzeevo_api.services.backup import rotate_master_key, run_due_backups
from tawzeevo_api.services.jobs import run_due_delivery_reminders
from tawzeevo_api.services.storefront_signals import rollup_views


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Tawzeevo encrypted backup jobs.")
    sub = command.add_subparsers(dest="job", required=True)
    sub.add_parser("run-due", help="Back up every connected tenant that is due.")
    sub.add_parser(
        "rollup-views", help="Fold storefront views older than 90 days into monthly counts."
    )
    sub.add_parser("run-reminders", help="Turn due delivery reminders into owner notifications.")
    rotate = sub.add_parser(
        "rotate-master-key",
        help="Re-wrap tenant keys from BACKUP_MASTER_KEY to BACKUP_MASTER_KEY_NEXT.",
    )
    rotate.add_argument("--new-kek-id", required=True)
    return command


def main() -> int:
    arguments = parser().parse_args()
    settings = get_settings()
    try:
        with SessionLocal() as db:
            if arguments.job == "run-due":
                done = run_due_backups(db, settings=settings)
                print(f"backups uploaded for {len(done)} tenant(s)")
            elif arguments.job == "rollup-views":
                print(f"rolled up {rollup_views(db)} view(s)")
            elif arguments.job == "run-reminders":
                print(f"sent {run_due_delivery_reminders(db)} reminder(s)")
            else:
                next_key = os.environ.get("BACKUP_MASTER_KEY_NEXT")
                if not next_key:
                    print("BACKUP_MASTER_KEY_NEXT is required", file=sys.stderr)
                    return 2
                count = rotate_master_key(
                    db, settings.backup_master_key or "", next_key, arguments.new_kek_id
                )
                print(f"re-wrapped {count} record(s) under {arguments.new_kek_id}")
    except AppError as error:
        print(f"{error.code}: {error.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
