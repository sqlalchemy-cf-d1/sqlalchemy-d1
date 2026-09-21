# sqlalchemy_d1/dialect.py
from sqlalchemy import text, types as sqltypes
from sqlalchemy.engine import reflection
from sqlalchemy_cloudflare_d1.dialect import (
    CloudflareD1Dialect,
    D1Boolean,
    D1Date,
    D1DateTime,
    D1Time,
)

from .type_compiler import D1TypeCompiler

INTERNAL_PREFIX = "_cf_"

# Checked in order, first match wins
TYPE_OVERRIDES = (
    ("DATETIME", D1DateTime),
    ("TIMESTAMP", D1DateTime),
    ("DATE", D1Date),
    ("TIME", D1Time),
    ("BOOL", D1Boolean),
)


class D1Dialect(CloudflareD1Dialect):
    name = "d1"
    type_compiler = D1TypeCompiler
    supports_statement_cache = True

    @reflection.cache
    def get_schema_names(self, connection, **kwargs):
        # D1 is built on SQLite, which only uses one schema
        return ["main"]

    @reflection.cache
    def get_table_names(self, connection, schema=None, **kw):
        """
        Return list of table names in the D1 database.
        """
        all_tables = super().get_table_names(connection, schema, **kw)
        # Filter out cloudflare tables
        visible_tables = [
            t for t in all_tables if not t.startswith(INTERNAL_PREFIX)
        ]
        return visible_tables

    @reflection.cache
    def get_view_names(self, connection, schema=None, **kw):
        """
        Return list of view names in the D1 database.
        """
        try:
            result = connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='view' ORDER BY name"
                )
            )
            all_views = [row[0] for row in result]
            visible_views = [
                v for v in all_views if not v.startswith(INTERNAL_PREFIX)
            ]
            return visible_views
        except Exception as e:
            raise RuntimeError(f"Failed to fetch view names: {e}")

    @reflection.cache
    def get_columns(self, connection, table_name, schema=None, **kw):
        """
        Return column info for a given table in D1.
        """
        columns = super().get_columns(connection, table_name, schema, **kw)
        pk_columns = [c for c in columns if c.get("primary_key")]
        for column in columns:
            column.setdefault(
                "autoincrement",
                len(pk_columns) == 1
                and column is pk_columns[0]
                and isinstance(column["type"], sqltypes.Integer),
            )
        return columns

    def _get_column_type(self, type_string):
        declared = (type_string or "").upper()
        for needle, sqla_type in TYPE_OVERRIDES:
            if needle in declared:
                return sqla_type()
        return super()._get_column_type(declared)
