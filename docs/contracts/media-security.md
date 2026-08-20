# Media security contract

Media storage remains provider-neutral. Before a production provider is approved, implementations use a safe local/development adapter behind the abstraction. Accepted product image formats are JPEG, PNG, and WebP; user SVG upload is prohibited. The server validates and re-encodes images, and tenant authorization applies to private media.
