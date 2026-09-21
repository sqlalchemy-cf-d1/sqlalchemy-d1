# sqlalchemy_d1/dialect.py
import re

from sqlalchemy import exc, text, types as sqltypes
from sqlalchemy.engine import reflection
from sqlalchemy_cloudflare_d1.dialect import CloudflareD1Dialect

from . import types as d1types

INTERNAL_PREFIX = "_cf_"

# Keyed by the first word of the declared type
DECLARED_TYPES = {
    "DATETIME": d1types.DATETIME,
    "TIMESTAMP": d1types.TIMESTAMP,
    "DATE": d1types.DATE,
    "TIME": d1types.TIME,
    "BOOLEAN": d1types.BOOLEAN,
    "BOOL": d1types.BOOLEAN,
    "DECIMAL": sqltypes.DECIMAL,
}

# Table options come after the last closing bracket of CREATE TABLE
WITHOUT_ROWID = re.compile(r"\bWITHOUT\s+ROWID\b[^)]*$", re.IGNORECASE)


def _visible(names):
    # Cloudflare keeps its own tables, such as _cf_KV, in the same database
    return [n for n in names if not n.startswith(INTERNAL_PREFIX)]


class D1Dialect(CloudflareD1Dialect):
    name = "d1"
    supports_statement_cache = True

    def create_connect_args(self, url):
        # URL format: d1://<account_id>:<api_token>@<database_id>
        # Query parameters are ignored. Upstream passes them to the driver,
        # where base_url would send the API token to any host.
        return (
            (),
            {
                "account_id": url.username,
                "api_token": url.password,
                "database_id": url.host,
            },
        )

    @reflection.cache
    def get_schema_names(self, connection, **kwargs):
        # D1 is built on SQLite, which only uses one schema
        return ["main"]

    @reflection.cache
    def get_table_names(self, connection, schema=None, **kw):
        """
        Return list of table names in the D1 database.
        """
        return _visible(super().get_table_names(connection, schema, **kw))

    @reflection.cache
    def get_view_names(self, connection, schema=None, **kw):
        """
        Return list of view names in the D1 database.
        """
        result = connection.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='view' ORDER BY name"
            )
        )
        return _visible([row[0] for row in result])

    @reflection.cache
    def get_view_definition(self, connection, view_name, schema=None, **kw):
        """
        Return the CREATE VIEW statement of a view.
        """
        result = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='view' AND name=:name"
            ),
            {"name": view_name},
        )
        row = result.first()
        if row is None:
            raise exc.NoSuchTableError(view_name)
        return row[0]

    @reflection.cache
    def has_table(self, connection, table_name, schema=None, **kw):
        """
        Return True if a table or a view with this name exists.
        """
        # Upstream only looks for tables. SQLAlchemy 2.0 expects views too
        result = connection.execute(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type IN ('table', 'view') AND name=:name "
                "AND name NOT LIKE 'sqlite_%'"
            ),
            {"name": table_name},
        )
        return result.first() is not None

    @reflection.cache
    def _get_table_info(self, connection, table_name, schema=None, **kw):
        # Rows are: cid, name, type, notnull, dflt_value, pk
        quoted = self.identifier_preparer.quote_identifier(table_name)
        result = connection.execute(text(f"PRAGMA table_info({quoted})"))
        return [tuple(row) for row in result]

    @reflection.cache
    def get_columns(self, connection, table_name, schema=None, **kw):
        """
        Return column info for a given table in D1.
        """
        rows = self._get_table_info(connection, table_name, schema, **kw)
        rowid_alias = self._get_rowid_alias(connection, table_name, rows)
        return [
            {
                "name": name,
                "type": self._get_column_type(declared),
                "nullable": not notnull,
                "default": default,
                "primary_key": bool(pk),
                "autoincrement": name == rowid_alias,
            }
            for _cid, name, declared, notnull, default, pk in rows
        ]

    @reflection.cache
    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        """
        Return the primary key columns in the order of the key.
        """
        rows = self._get_table_info(connection, table_name, schema, **kw)
        # pk is the position of the column inside the key, or 0
        pk_rows = sorted((r for r in rows if r[5]), key=lambda r: r[5])
        return {
            "constrained_columns": [r[1] for r in pk_rows],
            "name": None,
        }

    def get_check_constraints(self, connection, table_name, schema=None, **kw):
        # CHECK constraints are not reflected
        return []

    def get_table_comment(self, connection, table_name, schema=None, **kw):
        # SQLite has no table comments
        return {"text": None}

    def _get_rowid_alias(self, connection, table_name, rows):
        """
        Return the name of the column that SQLite fills in by itself.

        That is a single primary key column declared as exactly INTEGER,
        in a table that is not WITHOUT ROWID.
        """
        pk_rows = [r for r in rows if r[5]]
        if len(pk_rows) != 1:
            return None
        name, declared = pk_rows[0][1], pk_rows[0][2]
        if (declared or "").strip().upper() != "INTEGER":
            return None
        table_sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name=:name"
            ),
            {"name": table_name},
        ).scalar()
        if WITHOUT_ROWID.search(table_sql or ""):
            return None
        return name

    def _get_column_type(self, type_string):
        declared = (type_string or "").upper()
        # Only the first word counts, so UPDATED_INT stays an integer
        first_word = re.match(r"\s*(\w*)", declared).group(1)
        if first_word in DECLARED_TYPES:
            return DECLARED_TYPES[first_word]()
        return super()._get_column_type(declared)
