import inspect
import unittest
from datetime import date, datetime
from importlib.metadata import entry_points
from unittest import mock

from sqlalchemy import create_engine, types as sqltypes
from sqlalchemy.dialects import registry
from sqlalchemy.engine import make_url
from sqlalchemy_cloudflare_d1.compiler import CloudflareD1TypeCompiler
from sqlalchemy_cloudflare_d1.dialect import (
    CloudflareD1Dialect,
    D1Boolean,
    D1Date,
    D1DateTime,
    D1Time,
)

import sqlalchemy_d1
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
        self.assertEqual(sqlalchemy_d1.__version__, "0.2.0")

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

    def test_get_view_names_wraps_errors(self):
        def execute_impl(query, *args, **kwargs):
            raise ValueError("boom")

        conn = DummyConnection(execute_impl)

        with self.assertRaises(RuntimeError):
            self.dialect.get_view_names(conn)

    def test_get_column_type_maps_date_and_boolean_types(self):
        cases = [
            ("DATETIME", D1DateTime),
            ("datetime", D1DateTime),
            ("TIMESTAMP", D1DateTime),
            ("DATE", D1Date),
            ("TIME", D1Time),
            ("BOOLEAN", D1Boolean),
            ("BOOL", D1Boolean),
        ]
        for declared, expected in cases:
            self.assertIsInstance(
                self.dialect._get_column_type(declared), expected
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

    def test_get_columns_reflects_types_and_autoincrement(self):
        def execute_impl(query, *args, **kwargs):
            rows = [
                (0, "id", "INTEGER", 1, None, 1),
                (1, "name", "TEXT", 0, "'anonymous'", 0),
                (2, "created_at", "DATETIME", 0, None, 0),
                (3, "day", "DATE", 0, None, 0),
                (4, "is_active", "BOOLEAN", 1, "1", 0),
            ]
            return DummyResult(rows)

        conn = DummyConnection(execute_impl)

        cols = self.dialect.get_columns(conn, "mytable")

        self.assertEqual(
            [c["name"] for c in cols],
            ["id", "name", "created_at", "day", "is_active"],
        )
        self.assertIsInstance(cols[0]["type"], sqltypes.INTEGER)
        self.assertIsInstance(cols[1]["type"], sqltypes.TEXT)
        self.assertIsInstance(cols[2]["type"], D1DateTime)
        self.assertIsInstance(cols[3]["type"], D1Date)
        self.assertIsInstance(cols[4]["type"], D1Boolean)
        self.assertFalse(cols[0]["nullable"])
        self.assertEqual(cols[1]["default"], "'anonymous'")
        self.assertTrue(cols[0]["primary_key"])
        self.assertEqual(
            [c["autoincrement"] for c in cols],
            [True, False, False, False, False],
        )

    def test_autoincrement_false_for_composite_primary_key(self):
        def execute_impl(query, *args, **kwargs):
            rows = [
                (0, "a", "INTEGER", 1, None, 1),
                (1, "b", "INTEGER", 1, None, 2),
                (2, "c", "TEXT", 0, None, 0),
            ]
            return DummyResult(rows)

        conn = DummyConnection(execute_impl)

        cols = self.dialect.get_columns(conn, "mytable")
        self.assertEqual(
            [c["autoincrement"] for c in cols], [False, False, False]
        )

    def test_autoincrement_false_for_text_primary_key(self):
        def execute_impl(query, *args, **kwargs):
            rows = [
                (0, "code", "TEXT", 1, None, 1),
                (1, "amount", "INTEGER", 0, None, 0),
            ]
            return DummyResult(rows)

        conn = DummyConnection(execute_impl)

        cols = self.dialect.get_columns(conn, "mytable")
        self.assertEqual([c["autoincrement"] for c in cols], [False, False])


class UpstreamGuardTestSuite(unittest.TestCase):
    def test_get_column_type_takes_one_argument(self):
        params = inspect.signature(
            CloudflareD1Dialect._get_column_type
        ).parameters
        self.assertEqual(len(params), 2)

    def test_upstream_has_no_get_view_names(self):
        self.assertNotIn("get_view_names", vars(CloudflareD1Dialect))

    def test_type_compiler_has_visit_methods(self):
        for name in [
            "visit_DATETIME",
            "visit_TIMESTAMP",
            "visit_DATE",
            "visit_TIME",
            "visit_BOOLEAN",
        ]:
            self.assertTrue(callable(getattr(CloudflareD1TypeCompiler, name)))


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


if __name__ == "__main__":
    unittest.main()
