# API conventions

Production APIs use `/api/v1`. Mandatory evaluator routes remain at their exact root paths. Timestamps use RFC3339 and currencies use ISO codes. Authentication failures are `401`, authorization failures `403`, missing resources `404`, and state/uniqueness conflicts `409`; Pydantic validation retains `422` semantics. OpenAPI remains usable and password/hash values are never returned.
