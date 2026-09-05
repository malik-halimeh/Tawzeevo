# Tawzeevo starter master catalog

`open-food-facts-lebanon-v1.json` is a deliberately small, curated starter snapshot for the
Lebanon-market catalog foundation. It is not a claim of complete Lebanese retail coverage.

## Source and license

- Source: [Open Food Facts](https://world.openfoodfacts.org/data)
- Attribution: Open Food Facts contributors
- Database license: [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- Imported fields: product name, barcode, and source category
- Excluded fields: prices, nutrition, ingredients, personal data, and all Open Food Facts images

This snapshot and a database derived from it must retain Open Food Facts attribution and be shared
under ODbL-compatible terms. Tawzeevo's application source-code license is separate from the data
license.

## Curation and reproducibility

The snapshot records the source product URL, source revision, source last-modified timestamp,
retrieval timestamp, and a stable Tawzeevo import version. Bilingual master-category labels are a
Tawzeevo-authored mapping of the retained source categories.

The records were fetched individually from the documented product endpoint with the identifying
user agent `Tawzeevo/0.1 (https://github.com/malik-halimeh/Tawzeevo)`. No bulk page scraping or
image copying was used.

From the repository root, validate without changing PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m tawzeevo_api.cli.import_master_catalog --check-only --report data/master-catalog/open-food-facts-lebanon-v1.quality.json
```

After configuring `DATABASE_URL` and applying migrations, import idempotently:

```powershell
.\.venv\Scripts\python.exe -m tawzeevo_api.cli.import_master_catalog --report data/master-catalog/open-food-facts-lebanon-v1.quality.json
```

Reusing the same version and checksum is a no-op. Reusing a version with different content or
encountering a conflicting existing barcode identity aborts the transaction.
