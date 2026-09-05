from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    BarcodePackageLevel,
    MasterBarcode,
    MasterCatalogImport,
    MasterCategory,
    MasterProduct,
    MasterProductSource,
)

CATALOG_SCHEMA_VERSION = "catalog-import-v1"
APPROVED_SOURCE_NAME = "Open Food Facts"
APPROVED_SOURCE_LICENSE = "ODbL-1.0"
APPROVED_SOURCE_URL = "https://world.openfoodfacts.org/data"
APPROVED_LICENSE_URL = "https://opendatacommons.org/licenses/odbl/1-0"


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


class CatalogSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    license: str = Field(min_length=1, max_length=100)
    license_url: HttpUrl
    attribution: str = Field(min_length=1, max_length=300)
    retrieved_at: datetime

    @field_validator("name", "license", "attribution")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _normalized_text(value)


class CatalogCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_en: str = Field(min_length=1, max_length=200)
    name_ar: str = Field(min_length=1, max_length=200)

    @field_validator("name_en", "name_ar")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _normalized_text(value)


class CatalogRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    barcode: str = Field(min_length=8, max_length=14)
    product_name: str = Field(min_length=1, max_length=200)
    category: CatalogCategory
    source_categories: str = Field(min_length=1, max_length=1000)
    source_product_url: HttpUrl
    source_revision: int = Field(ge=1)
    source_last_modified_at: datetime

    @field_validator("barcode", "product_name", "source_categories")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _normalized_text(value)


class CatalogDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["catalog-import-v1"]
    import_version: str = Field(min_length=1, max_length=120)
    source: CatalogSource
    records: list[CatalogRecord] = Field(min_length=1)

    @field_validator("import_version")
    @classmethod
    def normalize_version(cls, value: str) -> str:
        return _normalized_text(value)


class CatalogQualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    record_index: int | None = None
    barcode: str | None = None
    message: str


class CatalogQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["PASS", "FAIL"]
    schema_version: str
    import_version: str
    total_records: int
    accepted_records: int
    rejected_records: int
    duplicate_barcodes: list[str]
    category_count: int
    issues: list[CatalogQualityIssue]


@dataclass(frozen=True)
class LoadedCatalogDataset:
    dataset: CatalogDataset
    sha256: str


@dataclass(frozen=True)
class CatalogImportResult:
    catalog_import_id: UUID
    import_version: str
    inserted_count: int
    reused_count: int
    already_imported: bool
    quality_report: CatalogQualityReport


def load_catalog_dataset(path: Path) -> LoadedCatalogDataset:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise AppError(
            400, "CATALOG_DATASET_UNREADABLE", "Catalog dataset could not be read"
        ) from exc
    try:
        dataset = CatalogDataset.model_validate_json(content)
    except ValidationError as exc:
        raise AppError(
            400,
            "CATALOG_DATASET_INVALID",
            "Catalog dataset does not match catalog-import-v1",
        ) from exc
    return LoadedCatalogDataset(
        dataset=dataset,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def is_valid_gtin(barcode: str) -> bool:
    if len(barcode) not in {8, 12, 13, 14} or not barcode.isascii() or not barcode.isdigit():
        return False
    payload = barcode[:-1]
    weighted_sum = sum(
        int(digit) * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(payload))
    )
    expected_check_digit = (10 - weighted_sum % 10) % 10
    return expected_check_digit == int(barcode[-1])


def analyze_catalog_dataset(dataset: CatalogDataset) -> CatalogQualityReport:
    issues: list[CatalogQualityIssue] = []
    global_failure = False
    barcode_counts = Counter(record.barcode for record in dataset.records)
    duplicate_barcodes = sorted(barcode for barcode, count in barcode_counts.items() if count > 1)
    for barcode in duplicate_barcodes:
        issues.append(
            CatalogQualityIssue(
                code="DUPLICATE_BARCODE",
                barcode=barcode,
                message="Barcode occurs more than once in this import version",
            )
        )

    if dataset.source.name != APPROVED_SOURCE_NAME:
        global_failure = True
        issues.append(
            CatalogQualityIssue(
                code="UNAPPROVED_SOURCE",
                message=f"Source must be {APPROVED_SOURCE_NAME}",
            )
        )
    if dataset.source.license != APPROVED_SOURCE_LICENSE:
        global_failure = True
        issues.append(
            CatalogQualityIssue(
                code="UNAPPROVED_LICENSE",
                message=f"Source license must be {APPROVED_SOURCE_LICENSE}",
            )
        )
    if str(dataset.source.url).rstrip("/") != APPROVED_SOURCE_URL:
        global_failure = True
        issues.append(
            CatalogQualityIssue(
                code="UNAPPROVED_SOURCE_URL",
                message=f"Source URL must be {APPROVED_SOURCE_URL}",
            )
        )
    if str(dataset.source.license_url).rstrip("/") != APPROVED_LICENSE_URL:
        global_failure = True
        issues.append(
            CatalogQualityIssue(
                code="UNAPPROVED_LICENSE_URL",
                message=f"License URL must be {APPROVED_LICENSE_URL}",
            )
        )

    rejected_indexes: set[int] = set()
    if global_failure:
        rejected_indexes.update(range(len(dataset.records)))
    for index, record in enumerate(dataset.records):
        if not is_valid_gtin(record.barcode):
            rejected_indexes.add(index)
            issues.append(
                CatalogQualityIssue(
                    code="INVALID_GTIN",
                    record_index=index,
                    barcode=record.barcode,
                    message="Barcode must be a valid GTIN-8, GTIN-12, GTIN-13, or GTIN-14",
                )
            )
        expected_url = f"https://world.openfoodfacts.org/product/{record.barcode}"
        if str(record.source_product_url).rstrip("/") != expected_url:
            rejected_indexes.add(index)
            issues.append(
                CatalogQualityIssue(
                    code="SOURCE_URL_MISMATCH",
                    record_index=index,
                    barcode=record.barcode,
                    message="Open Food Facts product URL must match the record barcode",
                )
            )
        if record.barcode in duplicate_barcodes:
            rejected_indexes.add(index)
        if record.source_last_modified_at > dataset.source.retrieved_at:
            rejected_indexes.add(index)
            issues.append(
                CatalogQualityIssue(
                    code="SOURCE_REVISION_AFTER_RETRIEVAL",
                    record_index=index,
                    barcode=record.barcode,
                    message="Source revision timestamp cannot be after dataset retrieval",
                )
            )

    rejected_count = len(rejected_indexes)
    return CatalogQualityReport(
        status="PASS" if not issues else "FAIL",
        schema_version=dataset.schema_version,
        import_version=dataset.import_version,
        total_records=len(dataset.records),
        accepted_records=len(dataset.records) - rejected_count,
        rejected_records=rejected_count,
        duplicate_barcodes=duplicate_barcodes,
        category_count=len(
            {(record.category.name_en, record.category.name_ar) for record in dataset.records}
        ),
        issues=issues,
    )


def _get_or_create_category(db: Session, record: CatalogRecord) -> MasterCategory:
    category = db.scalars(
        select(MasterCategory).where(
            MasterCategory.name_en == record.category.name_en,
            MasterCategory.name_ar == record.category.name_ar,
        )
    ).first()
    if category is None:
        category = MasterCategory(
            name_en=record.category.name_en,
            name_ar=record.category.name_ar,
        )
        db.add(category)
        db.flush()
    return category


def import_catalog_dataset(db: Session, loaded: LoadedCatalogDataset) -> CatalogImportResult:
    dataset = loaded.dataset
    quality_report = analyze_catalog_dataset(dataset)
    if quality_report.status != "PASS":
        raise AppError(
            400,
            "CATALOG_QUALITY_FAILED",
            "Catalog import was rejected by the quality gate",
        )

    existing_import = db.scalar(
        select(MasterCatalogImport).where(
            MasterCatalogImport.import_version == dataset.import_version
        )
    )
    if existing_import is not None:
        if existing_import.dataset_sha256 != loaded.sha256:
            raise AppError(
                409,
                "CATALOG_IMPORT_VERSION_CONFLICT",
                "This import version already exists with different content",
            )
        return CatalogImportResult(
            catalog_import_id=existing_import.id,
            import_version=existing_import.import_version,
            inserted_count=existing_import.inserted_count,
            reused_count=existing_import.reused_count,
            already_imported=True,
            quality_report=CatalogQualityReport.model_validate(existing_import.quality_report),
        )

    import_row = MasterCatalogImport(
        source_name=dataset.source.name,
        source_url=str(dataset.source.url),
        source_license=dataset.source.license,
        source_license_url=str(dataset.source.license_url),
        source_attribution=dataset.source.attribution,
        import_version=dataset.import_version,
        retrieved_at=dataset.source.retrieved_at,
        dataset_sha256=loaded.sha256,
        record_count=quality_report.total_records,
        inserted_count=0,
        reused_count=0,
        rejected_count=quality_report.rejected_records,
        duplicate_count=len(quality_report.duplicate_barcodes),
        quality_report=quality_report.model_dump(mode="json"),
    )
    db.add(import_row)
    try:
        db.flush()
    except Exception:
        db.rollback()
        raise

    inserted_count = 0
    reused_count = 0
    try:
        for record in dataset.records:
            category = _get_or_create_category(db, record)
            existing_barcode = db.scalar(
                select(MasterBarcode).where(MasterBarcode.barcode == record.barcode)
            )
            if existing_barcode is None:
                product = MasterProduct(
                    master_category_id=category.id,
                    name=record.product_name,
                )
                db.add(product)
                db.flush()
                db.add(
                    MasterBarcode(
                        master_product_id=product.id,
                        barcode=record.barcode,
                        package_level=BarcodePackageLevel.PIECE,
                    )
                )
                inserted_count += 1
            else:
                existing_product = db.get(MasterProduct, existing_barcode.master_product_id)
                if existing_product is None or (
                    existing_product.name != record.product_name
                    or existing_product.master_category_id != category.id
                ):
                    raise AppError(
                        409,
                        "MASTER_CATALOG_IDENTITY_CONFLICT",
                        f"Barcode {record.barcode} conflicts with an existing master product",
                    )
                product = existing_product
                reused_count += 1
            db.add(
                MasterProductSource(
                    master_product_id=product.id,
                    catalog_import_id=import_row.id,
                    source_product_id=record.barcode,
                    source_product_url=str(record.source_product_url),
                    source_categories=record.source_categories,
                    source_revision=str(record.source_revision),
                    source_last_modified_at=record.source_last_modified_at,
                )
            )
        import_row.inserted_count = inserted_count
        import_row.reused_count = reused_count
        db.commit()
    except Exception:
        db.rollback()
        raise

    return CatalogImportResult(
        catalog_import_id=import_row.id,
        import_version=import_row.import_version,
        inserted_count=inserted_count,
        reused_count=reused_count,
        already_imported=False,
        quality_report=quality_report,
    )
