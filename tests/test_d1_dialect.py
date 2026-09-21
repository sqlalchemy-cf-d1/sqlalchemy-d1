import importlib
import inspect
import unittest
from datetime import date, datetime
from importlib.metadata import PackageNotFoundError, entry_points, version
from unittest import mock

from sqlalchemy import create_engine, types as sqltypes
from sqlalchemy.dialects import registry
from sqlalchemy.engine import make_url
from sqlalchemy_cloudflare_d1.dialect import (
    CloudflareD1Dialect,
    D1Boolean,
    D1Date,
    D1DateTime,
    D1Time,
)

import sqlalchemy_d1
from sqlalchemy_d1 import types as d1types
from sqlalchemy_d1.dialect import D1Dialect


class DummyResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def fetchall(self):
        return self._rows


class DummyConnection:
    def __init__(self, execute_impl):
        self._execute_impl = execute_impl
        self.last_execute_args = None
        self.last_execute_kwargs = None

    def execute(self, query, *args, **kwargs):
        self.last_execute_args = (query, args)
        self.last_execute_kwargs = kwargs
        return self._execute_impl(query, *args, **kwargs)


class D1DialectTestSuite(unittest.TestCase):
    dialect = D1Dialect()

    def test_registry_loads_d1_dialect(self):
        self.assertIs(registry.load("d1"), D1Dialect)

    def test_entry_point_points_at_d1_dialect(self):
        eps = entry_points(group="sqlalchemy.dialects")
        self.assertEqual(eps["d1"].value, "sqlalchemy_d1.dialect:D1Dialect")

    def test_package_exports_dialect_and_version(self):
        self.assertIs(sqlalchemy_d1.D1Dialect, D1Dialect)
        self.assertEqual(sqlalchemy_d1.__version__, version("sqlalchemy-d1"))

    def test_package_imports_without_installed_metadata(self):
        self.addCleanup(importlib.reload, sqlalchemy_d1)

        with mock.patch(
            "importlib.metadata.version", side_effect=PackageNotFoundError
        ):
            importlib.reload(sqlalchemy_d1)

        self.assertEqual(sqlalchemy_d1.__version__, "0+unknown")
        self.assertIs(registry.load("d1"), D1Dialect)

    def test_create_engine_builds_d1_dialect(self):
        engine = create_engine("d1://acct:tok@dbid")

        self.assertIsInstance(engine.dialect, D1Dialect)
        self.assertIsInstance(engine.dialect, CloudflareD1Dialect)
        self.assertEqual(engine.dialect.name, "d1")

    def test_statement_cache_is_enabled(self):
        self.assertTrue(vars(D1Dialect)["supports_statement_cache"])

    def test_create_connect_args_parses_d1_url(self):
        url = make_url("d1://acct:tok@dbid")

        pos, kw = self.dialect.create_connect_args(url)

        self.assertEqual(pos, ())
        self.assertEqual(
            kw,
            {
                "account_id": "acct",
                "api_token": "tok",
                "database_id": "dbid",
            },
        )

    def test_get_schema_names_returns_main(self):
        conn = DummyConnection(lambda query, *args, **kwargs: DummyResult([]))

        self.assertEqual(self.dialect.get_schema_names(conn), ["main"])

    def test_get_table_names_filters_cf_internal_tables(self):
        conn = DummyConnection(lambda query, *args, **kwargs: DummyResult([]))

        with mock.patch.object(
            CloudflareD1Dialect,
            "get_table_names",
            return_value=["_cf_KV", "another_table", "test_table"],
        ):
            tables = self.dialect.get_table_names(conn)

        self.assertEqual(tables, ["another_table", "test_table"])

    def test_get_view_names_filters_cf_internal_views(self):
        def execute_impl(query, *args, **kwargs):
            rows = [
                ("_cf_view_internal",),
                ("my_view",),
            ]
            return DummyResult(rows)

        conn = DummyConnection(execute_impl)

        views = self.dialect.get_view_names(conn)
        self.assertEqual(views, ["my_view"])

    def test_get_view_names_returns_empty_list_without_views(self):
        conn = DummyConnection(lambda query, *args, **kwargs: DummyResult([]))

        self.assertEqual(self.dialect.get_view_names(conn), [])

    def test_get_view_names_lets_errors_propagate(self):
        def execute_impl(query, *args, **kwargs):
            raise ValueError("boom")

        conn = DummyConnection(execute_impl)

        with self.assertRaises(ValueError):
            self.dialect.get_view_names(conn)

    def test_get_column_type_maps_date_and_boolean_types(self):
        cases = [
            ("DATETIME", d1types.DATETIME, D1DateTime),
            ("datetime", d1types.DATETIME, D1DateTime),
            ("DATETIME(6)", d1types.DATETIME, D1DateTime),
            ("TIMESTAMP", d1types.TIMESTAMP, D1DateTime),
            ("TIMESTAMP WITH TIME ZONE", d1types.TIMESTAMP, D1DateTime),
            ("DATE", d1types.DATE, D1Date),
            ("TIME", d1types.TIME, D1Time),
            ("BOOLEAN", d1types.BOOLEAN, D1Boolean),
            ("BOOL", d1types.BOOLEAN, D1Boolean),
        ]
        for declared, expected, upstream_type in cases:
            sqla_type = self.dialect._get_column_type(declared)
            self.assertIs(type(sqla_type), expected)
            self.assertIsInstance(sqla_type, upstream_type)

    def test_get_column_type_maps_decimal_to_numeric(self):
        for declared in ["DECIMAL", "DECIMAL(10,2)", "decimal(10, 2)"]:
            self.assertIsInstance(
                self.dialect._get_column_type(declared), sqltypes.Numeric
            )

    def test_get_column_type_only_matches_the_first_word(self):
        cases = [
            ("UPDATED_INT", sqltypes.INTEGER),
            ("VALIDATED INT", sqltypes.INTEGER),
            ("DATETEXT", sqltypes.TEXT),
            ("BOOLEAN_TEXT", sqltypes.TEXT),
            ("MYDATE", sqltypes.TEXT),
        ]
        for declared, expected in cases:
            self.assertIs(
                type(self.dialect._get_column_type(declared)), expected
            )

    def test_get_column_type_leaves_other_types_to_upstream(self):
        upstream = CloudflareD1Dialect()
        for declared in ["VARCHAR(50)", "INTEGER", "REAL", "BLOB", "FOO", ""]:
            self.assertIs(
                type(self.dialect._get_column_type(declared)),
                type(upstream._get_column_type(declared)),
            )
        self.assertIsInstance(
            self.dialect._get_column_type("VARCHAR(50)"), sqltypes.TEXT
        )
        self.assertIsInstance(
            self.dialect._get_column_type("INTEGER"), sqltypes.INTEGER
        )
        self.assertIsInstance(
            self.dialect._get_column_type("REAL"), sqltypes.REAL
        )

    def test_get_column_type_handles_missing_type(self):
        self.assertIsInstance(
            self.dialect._get_column_type(None), sqltypes.TEXT
        )


class UpstreamGuardTestSuite(unittest.TestCase):
    def test_get_column_type_takes_one_argument(self):
        params = inspect.signature(
            CloudflareD1Dialect._get_column_type
        ).parameters
        self.assertEqual(len(params), 2)

    def test_upstream_has_no_view_reflection(self):
        self.assertNotIn("get_view_names", vars(CloudflareD1Dialect))
        self.assertNotIn("get_view_definition", vars(CloudflareD1Dialect))


class D1ResultProcessorTestSuite(unittest.TestCase):
    dialect = D1Dialect()
    messy_values = [1758448800, "", "09/21/2026", None]

    def test_datetime_parses_iso_string(self):
        process = D1DateTime().result_processor(self.dialect, None)
        self.assertEqual(
            process("2026-09-21 10:00:00"), datetime(2026, 9, 21, 10, 0)
        )

    def test_datetime_returns_messy_values_unchanged(self):
        process = D1DateTime().result_processor(self.dialect, None)
        for value in self.messy_values:
            self.assertEqual(process(value), value)

    def test_date_parses_iso_string(self):
        process = D1Date().result_processor(self.dialect, None)
        self.assertEqual(process("2026-09-21"), date(2026, 9, 21))

    def test_date_returns_messy_values_unchanged(self):
        process = D1Date().result_processor(self.dialect, None)
        for value in self.messy_values:
            self.assertEqual(process(value), value)

    def test_reflected_types_use_upstream_processors(self):
        process = d1types.TIMESTAMP().result_processor(self.dialect, None)
        self.assertEqual(
            process("2026-09-21 10:00:00"), datetime(2026, 9, 21, 10, 0)
        )

        process = d1types.BOOLEAN().bind_processor(self.dialect)
        self.assertEqual(process(True), 1)

        # The dialect must not swap a reflected type for the generic one
        for reflected in [d1types.DATETIME(), d1types.BOOLEAN()]:
            impl = reflected.dialect_impl(self.dialect)
            self.assertIs(type(impl), type(reflected))


if __name__ == "__main__":
    unittest.main()
