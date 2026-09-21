# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - Unreleased

### Changed

* Rewrote `D1Dialect` as a subclass of `CloudflareD1Dialect` from `sqlalchemy-cloudflare-d1`. The `d1://` connection string and the `d1` entry point are unchanged.
* Requires **SQLAlchemy 2.0** (`>=2.0,<2.1`). Version 0.1.0 stays available for SQLAlchemy 1.4.
* Lifted the Python cap. Python 3.11 or newer is supported.

### Added

* Real type names for bare `DATETIME`, `TIMESTAMP`, `DATE`, `TIME` and `BOOLEAN` types, so Apache Superset marks those columns as dates and booleans. Tables created through SQLAlchemy are still declared as `TEXT` and `INTEGER`, the same as upstream.
* Reflection of columns declared as `DATETIME`, `TIMESTAMP`, `DATE`, `TIME` or `BOOLEAN`.
* `autoincrement` on reflected columns.
* `get_view_names`, and `get_schema_names` returning `main`. Upstream has neither.
* Tables and views that start with `_cf_` are hidden from the table and view lists.
* `LICENSE` file and license metadata. The package is licensed under **Apache License 2.0**.
* Unit tests that run offline, integration tests against a real D1 database, and a CI workflow.

### Removed

* The dependency on `dbapi-d1`. The driver built into `sqlalchemy-cloudflare-d1` replaces it.
* The original reflection code and the empty `compiler.py` module.

## [0.1.0] - 2025-11-30

### Added

* First release. `D1Dialect` built on `DefaultDialect` with the `dbapi-d1` driver, for SQLAlchemy 1.4.
