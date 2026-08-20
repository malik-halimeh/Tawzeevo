# Repository scripts

Automation added here must be non-destructive, public-safe, and must not embed credentials. Milestone checks are exposed through the API `pyproject.toml` and root npm scripts. Safe database commands live with the API package: `tawzeevo_api.cli.create_admin` uses a hidden password prompt, and `tawzeevo_api.cli.seed_demo` requires an existing approved owner tenant and embeds no credentials.
