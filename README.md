# sqlalchemy-d1

A **SQLAlchemy dialect** for **Cloudflare D1** that keeps the `d1://` connection string working in **Apache Superset**.

Since version 0.2.0 this package is a thin layer over [sqlalchemy-cloudflare-d1](https://github.com/CollierKing/sqlalchemy-cloudflare-d1). That project is the real dialect and the real driver. This package registers it under the `d1` name and adds the few things Superset needs.

---

## Why this package exists

Superset ships a built-in **Cloudflare D1** engine spec that expects `d1://` connection strings. See the [Superset D1 docs page](https://superset.apache.org/user-docs/databases/supported/cloudflare-d1/).

Version 0.1.0 of this package only worked with SQLAlchemy 1.4. Superset has moved to SQLAlchemy 2.0, and its [UPDATING.md](https://github.com/apache/superset/blob/master/UPDATING.md) lists `d1` among the connectors that were held back because of that. Version 0.2.0 removes the block.

If you do not use Superset, install `sqlalchemy-cloudflare-d1` directly and use its `cloudflare_d1://` connection string.

---

## Installation

```bash
pip install sqlalchemy-d1
```

This also installs `sqlalchemy-cloudflare-d1` and SQLAlchemy 2.0. Python 3.11 or newer is required.

If your Superset still uses **SQLAlchemy 1.4** (Superset 6.1.0, for example), stay on version 0.1.0. Newer versions would upgrade SQLAlchemy and break it.

```bash
pip install "sqlalchemy-d1==0.1.0"
```

---

## Usage

```python
from sqlalchemy import create_engine, text

engine = create_engine("d1://<CF_ACCOUNT_ID>:<CF_API_TOKEN>@<D1_DB_ID>")

with engine.connect() as conn:
    print(conn.execute(text("SELECT 1")).scalar())
```

In Superset, use the same URL as the SQLAlchemy URI of the database connection.

---

## What it adds

| Feature | Description |
|---------|-------------|
| `d1://` name | Registers the upstream dialect under the `d1` name that Superset uses. Only the account, token and database ID are read from the URL. Query parameters are ignored. |
| Date and boolean reflection | Columns declared as `DATETIME`, `TIMESTAMP`, `DATE`, `TIME`, `BOOLEAN` or `BOOL` are reflected as the types in `sqlalchemy_d1.types`. They behave like the upstream date and boolean types and keep the declared name. Superset reads that name to decide if a column is a date. Upstream reflects these columns as `TEXT`. |
| `DECIMAL` reflection | Columns declared as `DECIMAL` are reflected as numeric. Upstream reflects them as `TEXT`. |
| `autoincrement` | Reflected columns report `autoincrement`. It is true only for the column SQLite fills in by itself: a single primary key column declared as `INTEGER`, in a table that is not `WITHOUT ROWID`. |
| Primary key order | A composite primary key is reflected in the order of the key, not the order of the columns. |
| Schemas and views | `get_schema_names` returns `main`, `get_view_names` lists views and `get_view_definition` returns the SQL of a view. Upstream has none of these. `has_table` is also true for a view. |
| Internal tables hidden | Tables and views that start with `_cf_`, such as `_cf_KV`, are left out of the lists. |

Everything else comes from `sqlalchemy-cloudflare-d1` unchanged. That includes the connection, the cursor, the SQL compiler, and the reflection of foreign keys, indexes and unique constraints.

---

## Known limits

Tables **created through SQLAlchemy** are identical to the ones upstream creates. A `DateTime` column is declared as `TEXT` and a `Boolean` column as `INTEGER`, so they are reflected as text and integer afterwards. Values still round trip correctly when you use the same `Table` object.

Tables created with plain SQL and a `DATETIME` column, which is the normal case for D1, are reflected as dates. A table reflected from D1 keeps its declared types when SQLAlchemy creates it again.

Only the first word of a declared type is matched, so `TIMESTAMP WITH TIME ZONE` is a date and `UPDATED_INT` is an integer.

**CHECK constraints** are not reflected. `get_check_constraints` returns an empty list, and `get_table_comment` returns no comment because SQLite has none.

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

With **Poetry**, run `poetry install --all-extras` instead.

Run the checks:

```bash
ruff check . && ruff format --check . && mypy src
pytest -m "not integration" --disable-socket
```

The integration tests need a real D1 database. Use a throwaway one. They create and drop their own tables.

```bash
export CF_ACCOUNT_ID=<CF_ACCOUNT_ID>
export CF_API_TOKEN=<CF_API_TOKEN>
export CF_D1_DATABASE_ID=<D1_DB_ID>
pytest -m integration
```

---

## License

This package is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).

`sqlalchemy-cloudflare-d1` is a separate project under the MIT license. It is a dependency and none of its code is copied here.
