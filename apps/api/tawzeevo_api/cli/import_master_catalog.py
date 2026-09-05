from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.database import SessionLocal
from tawzeevo_api.errors import AppError
from tawzeevo_api.services.catalog_import import (
    CatalogQualityReport,
    analyze_catalog_dataset,
    import_catalog_dataset,
    load_catalog_dataset,
)

DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "master-catalog"
    / "open-food-facts-lebanon-v1.json"
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Validate and import a versioned Tawzeevo master-catalog snapshot."
    )
    command.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    command.add_argument("--report", type=Path)
    command.add_argument(
        "--check-only",
        action="store_true",
        help="Run the quality gate without changing PostgreSQL.",
    )
    return command


def _write_report(path: Path | None, report: CatalogQualityReport) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(db_factory: sessionmaker[Session] | None = None) -> int:
    arguments = parser().parse_args()
    try:
        loaded = load_catalog_dataset(arguments.dataset)
        quality_report = analyze_catalog_dataset(loaded.dataset)
        _write_report(arguments.report, quality_report)
        if quality_report.status != "PASS":
            print(json.dumps(quality_report.model_dump(mode="json"), ensure_ascii=False))
            return 1
        if arguments.check_only:
            print(json.dumps(quality_report.model_dump(mode="json"), ensure_ascii=False))
            return 0
        factory = db_factory or SessionLocal
        with factory() as db:
            result = import_catalog_dataset(db, loaded)
    except AppError as exc:
        print(f"Master catalog was not imported: {exc.code} — {exc.message}")
        return 1
    action = "already imported" if result.already_imported else "imported"
    print(
        f"Catalog {result.import_version} {action}: "
        f"{result.inserted_count} inserted, {result.reused_count} reused."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
