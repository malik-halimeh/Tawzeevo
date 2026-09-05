from __future__ import annotations

import json
import sys

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.cli import import_master_catalog
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    MasterBarcode,
    MasterCatalogImport,
    MasterCategory,
    MasterProduct,
    MasterProductSource,
)
from tawzeevo_api.services.catalog_import import (
    LoadedCatalogDataset,
    analyze_catalog_dataset,
    import_catalog_dataset,
    load_catalog_dataset,
)


def test_catalog_quality_gate_reports_invalid_and_duplicate_gtins() -> None:
    loaded = load_catalog_dataset(import_master_catalog.DEFAULT_DATASET_PATH)
    clean_report = analyze_catalog_dataset(loaded.dataset)
    assert clean_report.status == "PASS"
    assert clean_report.total_records == 4
    assert clean_report.accepted_records == 4
    assert clean_report.category_count == 2
    assert clean_report.issues == []

    first = loaded.dataset.records[0]
    invalid = first.model_copy(
        update={
            "barcode": "5283003200011",
            "source_product_url": "https://world.openfoodfacts.org/product/5283003200011",
        }
    )
    bad_dataset = loaded.dataset.model_copy(update={"records": [first, first, invalid]})
    report = analyze_catalog_dataset(bad_dataset)
    assert report.status == "FAIL"
    assert report.accepted_records == 0
    assert report.rejected_records == 3
    assert report.duplicate_barcodes == ["5283003200010"]
    assert {issue.code for issue in report.issues} == {
        "DUPLICATE_BARCODE",
        "INVALID_GTIN",
    }


def test_catalog_import_persists_provenance_is_idempotent_and_rolls_back_conflicts(
    session_factory: sessionmaker[Session],
) -> None:
    loaded = load_catalog_dataset(import_master_catalog.DEFAULT_DATASET_PATH)
    with session_factory() as db:
        imported = import_catalog_dataset(db, loaded)
        assert imported.already_imported is False
        assert imported.inserted_count == 4
        assert imported.reused_count == 0

        replay = import_catalog_dataset(db, loaded)
        assert replay.already_imported is True
        assert replay.catalog_import_id == imported.catalog_import_id

        with pytest.raises(AppError) as version_conflict:
            import_catalog_dataset(
                db,
                LoadedCatalogDataset(dataset=loaded.dataset, sha256="0" * 64),
            )
        assert version_conflict.value.code == "CATALOG_IMPORT_VERSION_CONFLICT"

        renamed_record = loaded.dataset.records[0].model_copy(
            update={"product_name": "Conflicting identity"}
        )
        conflicting_dataset = loaded.dataset.model_copy(
            update={
                "import_version": "off-lebanon-conflict-v2",
                "records": [renamed_record],
            }
        )
        with pytest.raises(AppError) as identity_conflict:
            import_catalog_dataset(
                db,
                LoadedCatalogDataset(dataset=conflicting_dataset, sha256="1" * 64),
            )
        assert identity_conflict.value.code == "MASTER_CATALOG_IDENTITY_CONFLICT"

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(MasterCatalogImport)) == 1
        assert db.scalar(select(func.count()).select_from(MasterCategory)) == 2
        assert db.scalar(select(func.count()).select_from(MasterProduct)) == 4
        assert db.scalar(select(func.count()).select_from(MasterBarcode)) == 4
        assert db.scalar(select(func.count()).select_from(MasterProductSource)) == 4
        import_row = db.scalar(select(MasterCatalogImport))
        source_row = db.scalar(select(MasterProductSource))
        assert import_row is not None
        assert import_row.source_name == "Open Food Facts"
        assert import_row.source_license == "ODbL-1.0"
        assert import_row.source_attribution == "Open Food Facts contributors"
        assert import_row.import_version == "off-lebanon-2026-08-26-v1"
        assert import_row.record_count == 4
        assert import_row.quality_report["status"] == "PASS"
        assert source_row is not None
        assert source_row.source_product_url.startswith("https://world.openfoodfacts.org/product/")
        assert source_row.source_categories


def test_catalog_cli_check_only_writes_quality_report_without_database_changes(
    monkeypatch: object,
    capsys: object,
    tmp_path: object,
    session_factory: sessionmaker[Session],
) -> None:
    report_path = tmp_path / "quality.json"  # type: ignore[operator]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        sys,
        "argv",
        [
            "import-master-catalog",
            "--dataset",
            str(import_master_catalog.DEFAULT_DATASET_PATH),
            "--report",
            str(report_path),
            "--check-only",
        ],
    )
    assert import_master_catalog.main(session_factory) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["accepted_records"] == 4
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(MasterCatalogImport)) == 0
    assert '"status": "PASS"' in capsys.readouterr().out  # type: ignore[attr-defined]
