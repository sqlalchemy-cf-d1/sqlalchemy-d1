<div align="center">

# sqlalchemy-d1

A **SQLAlchemy dialect** for **Cloudflare D1** that keeps the `d1://` connection string working in **Apache Superset**.

[![PyPI](https://img.shields.io/pypi/v/sqlalchemy-d1)](https://pypi.org/project/sqlalchemy-d1/) [![Python](https://img.shields.io/pypi/pyversions/sqlalchemy-d1)](https://pypi.org/project/sqlalchemy-d1/) [![CI](https://github.com/sqlalchemy-cf-d1/sqlalchemy-d1/actions/workflows/ci.yml/badge.svg)](https://github.com/sqlalchemy-cf-d1/sqlalchemy-d1/actions/workflows/ci.yml) [![License](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/sqlalchemy-cf-d1/sqlalchemy-d1/blob/main/LICENSE) [![Superset docs](https://img.shields.io/badge/Superset%20docs-Cloudflare%20D1-20A7C9)](https://superset.apache.org/user-docs/databases/supported/cloudflare-d1/)

[PyPI](https://pypi.org/project/sqlalchemy-d1/) · [Changelog](https://github.com/sqlalchemy-cf-d1/sqlalchemy-d1/blob/main/CHANGELOG.md) · [Superset D1 docs](https://superset.apache.org/user-docs/databases/supported/cloudflare-d1/) · [Issues](https://github.com/sqlalchemy-cf-d1/sqlalchemy-d1/issues)

</div>

<br>

Since version 0.2.0 this package is a thin layer over [sqlalchemy-cloudflare-d1](https://github.com/CollierKing/sqlalchemy-cloudflare-d1). That project is the real dialect and the real driver. This package registers it under the `d1` name and adds the few things Superset needs.

## Why this package exists

Superset ships a built-in **Cloudflare D1** engine spec that expects `d1://` connection strings. See the [Superset D1 docs page](https://superset.apache.org/user-docs/databases/supported/cloudflare-d1/).

Version 0.1.0 of this package only worked with SQLAlchemy 1.4. When Superset moved to SQLAlchemy 2.0, it held its `d1` extra back because of that. Version 0.2.0 works with SQLAlchemy 2.0. Since [apache/superset#44505](https://github.com/apache/superset/pull/44505), merged on 29 September 2026, the `d1` extra installs this package alone. See Superset's [UPDATING.md](https://github.com/apache/superset/blob/master/UPDATING.md).

> **Not using Superset?** Install `sqlalchemy-cloudflare-d1` directly and use its `cloudflare_d1://` connection string.

## Installation

```bash
pip install sqlalchemy-d1
```

This also installs `sqlalchemy-cloudflare-d1` and SQLAlchemy 2.0. Python 3.11 or newer is required.

> **Superset on SQLAlchemy 1.4?** Superset 6.1.0, for example. Stay on version 0.1.0. Newer versions would upgrade SQLAlchemy and break it.
>
> ```bash
> pip install "sqlalchemy-d1==0.1.0"
> ```

### Compatibility

| sqlalchemy-d1 | SQLAlchemy | Python | Driver |
|---------------|------------|--------|--------|
| **0.2.x** | 2.0 | 3.11 or newer | `sqlalchemy-cloudflare-d1` |
| **0.1.0** | 1.4 | 3.11 | `dbapi-d1` |

## Usage

### Connection string

```
d1://<CF_ACCOUNT_ID>:<CF_API_TOKEN>@<D1_DB_ID>
```

| Part | Value |
|------|-------|
| `CF_ACCOUNT_ID` | Your Cloudflare account ID |
| `CF_API_TOKEN` | A Cloudflare [API token](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/) with access to D1 |
| `D1_DB_ID` | The ID of your D1 database |

### SQLAlchemy

```python
from sqlalchemy import create_engine, text

engine = create_engine("d1://<CF_ACCOUNT_ID>:<CF_API_TOKEN>@<D1_DB_ID>")

with engine.connect() as conn:
    print(conn.execute(text("SELECT 1")).scalar())
```

### Apache Superset

In Superset, open **Settings > Database Connections > + Database** and use the same URL as the SQLAlchemy URI of the database connection. Your tables are listed under the `main` schema.

## What it adds

| Feature | Description |
|---------|-------------|
| `d1://` name | Registers the upstream dialect under the `d1` name that Superset uses. |
| Date and boolean reflection | Columns declared as `DATETIME`, `TIMESTAMP`, `DATE`, `TIME`, `BOOLEAN` or `BOOL` are reflected as the types in `sqlalchemy_d1.types`. They behave like the upstream date and boolean types and keep the declared name. Superset reads that name to decide if a column is a date. Upstream reflects these columns as `TEXT`. |
| `DECIMAL` reflection | Columns declared as `DECIMAL` are reflected as numeric. Upstream reflects them as `TEXT`. |
| `autoincrement` | Reflected columns report `autoincrement`. It is true only for the column SQLite fills in by itself: a single primary key column declared as `INTEGER`, in a table that is not `WITHOUT ROWID`. |
| Primary key order | A composite primary key is reflected in the order of the key, not the order of the columns. |
| Schemas and views | `get_schema_names` returns `main`, `get_view_names` lists views and `get_view_definition` returns the SQL of a view. Upstream has none of these. `has_table` is also true for a view. |
| Internal tables hidden | Tables and views that start with `_cf_`, such as `_cf_KV`, are left out of the lists. |

Everything else comes from `sqlalchemy-cloudflare-d1` unchanged. That includes the connection, the cursor, the SQL compiler, and the reflection of foreign keys, indexes and unique constraints.

## Known limits

### In this package

* **Tables created through SQLAlchemy** are identical to the ones upstream creates. A `DateTime` column is declared as `TEXT` and a `Boolean` column as `INTEGER`, so they are reflected as text and integer afterwards. Values still round trip correctly when you use the same `Table` object.
* **Tables created with plain SQL** and a `DATETIME` column, which is the normal case for D1, are reflected as dates. A table reflected from D1 keeps its declared types when SQLAlchemy creates it again on D1. On another database the same columns compile like SQLAlchemy's generic date and boolean types.
* **Only the first word of a declared type is matched**, so `TIMESTAMP WITH TIME ZONE` is a date and `UPDATED_INT` is an integer.
* **CHECK constraints** are not reflected. `get_check_constraints` returns an empty list, and `get_table_comment` returns no comment because SQLite has none.

### From sqlalchemy-cloudflare-d1

These come from the upstream driver and dialect, so this package has them too.

* **Columns with the same name** all get the value of the last one, without an error. `SELECT a.id, b.id FROM a JOIN b ...` returns `b.id` twice, and so does `SELECT *` over a join where both tables have an `id`. Give the columns different names with `AS`. Reported as [#31](https://github.com/CollierKing/sqlalchemy-cloudflare-d1/issues/31).
* **Statements that do not start with `SELECT`, `PRAGMA` or `WITH`**, and have no `RETURNING`, come back without column names, so SQLAlchemy raises `This result object does not return rows`. That includes a query that starts with a comment, `EXPLAIN QUERY PLAN` and `VALUES`. Put a leading comment at the end of the query instead, with no semicolon after it. Reported as [#32](https://github.com/CollierKing/sqlalchemy-cloudflare-d1/issues/32).
* **Date and time values are written with a `T`**, such as `2026-09-21T09:00:00`. Data from other tools often has a space instead, and Superset writes its time filters with a space. SQLite compares both forms as text and a `T` sorts after a space, so comparing one form with the other can give the wrong rows. Keep dates in one form. SQLite's `datetime()` turns either form into the one with a space.

## Development

### Setup

```bash
git clone https://github.com/sqlalchemy-cf-d1/sqlalchemy-d1.git
cd sqlalchemy-d1
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

With **Poetry**, run `poetry install --all-extras` instead.

### Checks

```bash
ruff check . && ruff format --check . && mypy src
pytest -m "not integration" --disable-socket
```

### Integration tests

The integration tests need a real D1 database. Use a throwaway one. They create and drop their own tables.

```bash
export CF_ACCOUNT_ID=<CF_ACCOUNT_ID>
export CF_API_TOKEN=<CF_API_TOKEN>
export CF_D1_DATABASE_ID=<D1_DB_ID>
pytest -m integration
```

## Contributing

Issues and pull requests are welcome on [GitHub](https://github.com/sqlalchemy-cf-d1/sqlalchemy-d1). CI runs the checks and unit tests above on Python 3.11 to 3.14 for every pull request. It also runs them once a week, so a new upstream release that breaks the dialect is noticed.

Some changes belong in another project:

| Change | Where |
|--------|-------|
| The `d1://` dialect and its reflection | This repository |
| The D1 engine spec in Superset | [apache/superset](https://github.com/apache/superset) |
| The DBAPI driver, the cursor and the SQL compiler | [CollierKing/sqlalchemy-cloudflare-d1](https://github.com/CollierKing/sqlalchemy-cloudflare-d1) |

## License

This package is licensed under the **Apache License 2.0**. See [LICENSE](https://github.com/sqlalchemy-cf-d1/sqlalchemy-d1/blob/main/LICENSE).

`sqlalchemy-cloudflare-d1` is a separate project under the MIT license. It is a dependency and none of its code is copied here.
