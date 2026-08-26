# Media security contract

Media storage remains provider-neutral. Before a production provider is approved, implementations use a safe local/development adapter behind the abstraction. Accepted product image formats are JPEG, PNG, and WebP; user SVG upload is prohibited. The server validates and re-encodes images, and tenant authorization applies to private media.

The Phase 2 adapter writes opaque object keys below `MEDIA_LOCAL_ROOT`. It rejects path traversal,
limits upload bytes and decoded dimensions, decodes the declared JPEG/PNG/WebP input, applies EXIF
orientation, and re-encodes the result as WebP so uploaded metadata and untrusted original bytes are
not served back. Image content responses require an active owner membership and use `nosniff`.

This local adapter is safe for development and demonstrations but is not durable on an ephemeral
Render filesystem. Selecting and configuring durable production object storage remains a separate,
explicit provider decision; the database stores provider-neutral object metadata and keys so the
adapter can be replaced without changing catalog meaning.
