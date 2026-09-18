from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import MasterProductImage, TenantProduct, TenantProductImage
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope

ACCEPTED_IMAGE_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
ACCEPTED_PIL_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
OUTPUT_CONTENT_TYPE = "image/webp"


class ObjectStorage(Protocol):
    def put_bytes(self, object_key: str, content: bytes) -> None: ...

    def get_bytes(self, object_key: str) -> bytes: ...

    def delete(self, object_key: str) -> None: ...


class LocalObjectStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, object_key: str) -> Path:
        target = (self.root / object_key).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise AppError(400, "INVALID_MEDIA_KEY", "Media object key is invalid") from exc
        return target

    def put_bytes(self, object_key: str, content: bytes) -> None:
        target = self._safe_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
                temporary.write(content)
                temporary.flush()
                temporary_path = Path(temporary.name)
            temporary_path.replace(target)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def get_bytes(self, object_key: str) -> bytes:
        target = self._safe_path(object_key)
        try:
            return target.read_bytes()
        except FileNotFoundError as exc:
            raise AppError(404, "MEDIA_CONTENT_NOT_FOUND", "Media content was not found") from exc

    def delete(self, object_key: str) -> None:
        target = self._safe_path(object_key)
        target.unlink(missing_ok=True)


@lru_cache
def get_object_storage() -> ObjectStorage:
    settings = get_settings()
    return LocalObjectStorage(Path(settings.media_local_root))


@dataclass(frozen=True)
class ProcessedImage:
    content: bytes
    content_type: str
    width: int
    height: int
    sha256: str


def process_product_image(content: bytes, declared_content_type: str | None) -> ProcessedImage:
    settings = get_settings()
    if declared_content_type not in ACCEPTED_IMAGE_CONTENT_TYPES:
        raise AppError(
            415,
            "UNSUPPORTED_IMAGE_TYPE",
            "Product images must be JPEG, PNG, or WebP",
        )
    if not content:
        raise AppError(400, "EMPTY_IMAGE", "Product image is empty")
    if len(content) > settings.media_max_upload_bytes:
        raise AppError(413, "IMAGE_TOO_LARGE", "Product image exceeds the upload size limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as opened:
                if opened.format not in ACCEPTED_PIL_FORMATS:
                    raise AppError(
                        415,
                        "UNSUPPORTED_IMAGE_TYPE",
                        "Product images must be JPEG, PNG, or WebP",
                    )
                source_width, source_height = opened.size
                if (
                    source_width > settings.media_max_dimension
                    or source_height > settings.media_max_dimension
                ):
                    raise AppError(
                        413,
                        "IMAGE_DIMENSIONS_TOO_LARGE",
                        "Product image dimensions exceed the safety limit",
                    )
                opened.load()
                image = ImageOps.exif_transpose(opened)
                width, height = image.size
                if width > settings.media_max_dimension or height > settings.media_max_dimension:
                    raise AppError(
                        413,
                        "IMAGE_DIMENSIONS_TOO_LARGE",
                        "Product image dimensions exceed the safety limit",
                    )
                has_alpha = image.mode in {"RGBA", "LA"} or (
                    image.mode == "P" and "transparency" in image.info
                )
                normalized = image.convert("RGBA" if has_alpha else "RGB")
                output = BytesIO()
                normalized.save(
                    output,
                    format="WEBP",
                    lossless=has_alpha,
                    quality=85,
                    method=4,
                )
    except AppError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise AppError(
            413,
            "IMAGE_DIMENSIONS_TOO_LARGE",
            "Product image dimensions exceed the safety limit",
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AppError(400, "INVALID_IMAGE", "Product image could not be decoded") from exc
    encoded = output.getvalue()
    if len(encoded) > settings.media_max_upload_bytes:
        raise AppError(413, "IMAGE_TOO_LARGE", "Processed product image exceeds the size limit")
    return ProcessedImage(
        content=encoded,
        content_type=OUTPUT_CONTENT_TYPE,
        width=width,
        height=height,
        sha256=hashlib.sha256(encoded).hexdigest(),
    )


def list_master_product_images(db: Session, master_product_id: UUID) -> list[MasterProductImage]:
    return list(
        db.scalars(
            select(MasterProductImage)
            .where(MasterProductImage.master_product_id == master_product_id)
            .order_by(
                MasterProductImage.display_order.asc(),
                MasterProductImage.created_at.asc(),
                MasterProductImage.id.asc(),
            )
        )
    )


def list_tenant_product_images(
    db: Session, tenant_id: UUID, product_id: UUID
) -> list[TenantProductImage]:
    return list(
        db.scalars(
            select(TenantProductImage)
            .where(
                TenantProductImage.tenant_id == tenant_id,
                TenantProductImage.tenant_product_id == product_id,
            )
            .order_by(
                TenantProductImage.display_order.asc(),
                TenantProductImage.created_at.asc(),
                TenantProductImage.id.asc(),
            )
        )
    )


def upload_tenant_product_image(
    db: Session,
    storage: ObjectStorage,
    tenant_id: UUID,
    product_id: UUID,
    processed: ProcessedImage,
    *,
    alt_text: str | None,
    display_order: int,
) -> TenantProductImage:
    product_exists = db.scalar(
        select(TenantProduct.id).where(
            TenantProduct.id == product_id, TenantProduct.tenant_id == tenant_id
        )
    )
    if product_exists is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Product was not found")
    # Idempotent retry (PHASE_04.md K): the same bytes for the same product map to the existing
    # asset, so a device that lost the upload response never creates a duplicate.
    duplicate = db.scalar(
        select(TenantProductImage).where(
            TenantProductImage.tenant_id == tenant_id,
            TenantProductImage.tenant_product_id == product_id,
            TenantProductImage.sha256 == processed.sha256,
        )
    )
    if duplicate is not None:
        return duplicate
    object_key = f"tenants/{tenant_id}/products/{product_id}/{uuid4()}.webp"
    image = TenantProductImage(
        tenant_id=tenant_id,
        tenant_product_id=product_id,
        object_key=object_key,
        content_type=processed.content_type,
        byte_size=len(processed.content),
        width=processed.width,
        height=processed.height,
        display_order=display_order,
        alt_text=(alt_text.strip() or None) if alt_text is not None else None,
        sha256=processed.sha256,
    )
    storage.put_bytes(object_key, processed.content)
    db.add(image)
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
    except Exception:
        db.rollback()
        storage.delete(object_key)
        raise
    db.refresh(image)
    return image


def get_tenant_image_content(
    db: Session,
    storage: ObjectStorage,
    tenant_id: UUID,
    image_id: UUID,
) -> tuple[TenantProductImage, bytes]:
    image = db.scalar(
        select(TenantProductImage).where(
            TenantProductImage.id == image_id,
            TenantProductImage.tenant_id == tenant_id,
        )
    )
    if image is None:
        raise AppError(404, "PRODUCT_IMAGE_NOT_FOUND", "Product image was not found")
    return image, storage.get_bytes(image.object_key)


def get_master_image_content(
    db: Session,
    storage: ObjectStorage,
    image_id: UUID,
) -> tuple[MasterProductImage, bytes]:
    image = db.get(MasterProductImage, image_id)
    if image is None:
        raise AppError(404, "PRODUCT_IMAGE_NOT_FOUND", "Product image was not found")
    return image, storage.get_bytes(image.object_key)
