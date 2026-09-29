# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-09-21

### Changed

* Rewrote `D1Dialect` as a subclass of `CloudflareD1Dialect` from `sqlalchemy-cloudflare-d1`. The `d1://` connection string and the `d1` entry point are unchanged.
* Requires **SQLAlchemy 2.0** (`>=2.0,<2.1`). Version 0.1.0 stays available for SQLAlchemy 1.4.
* Lifted the Python cap. Python 3.11 or newer is supported.
* Reflection errors are no longer wrapped in `RuntimeError`. SQLAlchemy errors reach the caller unchanged.
* `get_view_definition` returns the SQL of the view and raises `NoSuchTableError` for a missing view. It returned `None` before. `get_table_comment` returns `{"text": None}` instead of an empty string.
* `has_table` is also true for a view, which is what SQLAlchemy 2.0 expects.

### Added

* Reflection of columns declared as `DATETIME`, `TIMESTAMP`, `DATE`, `TIME`, `BOOLEAN` or `BOOL`. They are reflected as the new types in `sqlalchemy_d1.types`, which keep the declared name on the `d1` dialect, so Apache Superset marks those columns as dates and booleans. On other dialects they compile like the generic types. Generic types compile the same as upstream, so tables created through SQLAlchemy are still declared as `TEXT` and `INTEGER`.
* `autoincrement` on reflected columns. It is true only for a single primary key column declared as `INTEGER`, in a table that is not `WITHOUT ROWID`.
* `get_view_names`, `get_view_definition`, and `get_schema_names` returning `main`. Upstream has none of these.
* Tables and views that start with `_cf_` are hidden from the table and view lists.
* `LICENSE` file and license metadata. The package is licensed under **Apache License 2.0**.
* Unit tests that run offline, integration tests against a real D1 database, and a CI workflow.

### Fixed

* A composite primary key is reflected in the order of the key. Version 0.1.0 returned it in column order.

### Removed

* The dependency on `dbapi-d1`. The driver built into `sqlalchemy-cloudflare-d1` replaces it.
* The original reflection code and the empty `compiler.py` module.

## [0.1.0] - 2025-11-30

### Added

* First release. `D1Dialect` built on `DefaultDialect` with the `dbapi-d1` driver, for SQLAlchemy 1.4.
