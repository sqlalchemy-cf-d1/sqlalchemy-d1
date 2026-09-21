import os
import unittest
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    create_engine,
    inspect,
    select,
    text,
    types as sqltypes,
)
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy_cloudflare_d1.dialect import D1Boolean, D1Date, D1DateTime

COLUMN_NAMES = ["id", "name", "created_at", "day", "active"]


@pytest.mark.integration
@unittest.skipUnless(
    os.environ.get("CF_D1_DATABASE_ID"), "CF_D1_DATABASE_ID is not set"
)
class D1IntegrationTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suffix = uuid.uuid4().hex[:8]
        cls.table_name = f"sqlalchemy_d1_test_{cls.suffix}"
        cls.view_name = f"sqlalchemy_d1_test_view_{cls.suffix}"
        cls.engine = create_engine(
            URL.create(
                "d1",
                username=os.environ["CF_ACCOUNT_ID"],
                password=os.environ["CF_API_TOKEN"],
                host=os.environ["CF_D1_DATABASE_ID"],
            )
        )
        cls.addClassCleanup(cls.drop_all)
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    f"CREATE TABLE {cls.table_name} ("
                    "id INTEGER PRIMARY KEY, name TEXT, "
                    "created_at DATETIME, day DATE, active BOOLEAN)"
                )
            )
            conn.execute(
                text(
                    f"INSERT INTO {cls.table_name} "
                    "(id, name, created_at, day, active) VALUES "
                    "(:id, :name, :created_at, :day, :active)"
                ),
                [
                    {
                        "id": 1,
                        "name": "first",
                        "created_at": "2026-09-21 10:00:00",
                        "day": "2026-09-21",
                        "active": 1,
                    },
                    {
                        "id": 2,
                        "name": "second",
                        "created_at": "2026-09-22 11:30:00",
                        "day": "2026-09-22",
                        "active": 0,
                    },
                ],
            )
            conn.execute(
                text(
                    f"CREATE VIEW {cls.view_name} AS "
                    f"SELECT id, name, created_at FROM {cls.table_name}"
                )
            )

    @classmethod
    def drop_all(cls):
        with cls.engine.begin() as conn:
            conn.execute(text(f"DROP VIEW IF EXISTS {cls.view_name}"))
            conn.execute(text(f"DROP TABLE IF EXISTS {cls.table_name}"))
        cls.engine.dispose()

    def test_get_columns_reflects_declared_types(self):
        cols = inspect(self.engine).get_columns(self.table_name)

        self.assertEqual([c["name"] for c in cols], COLUMN_NAMES)
        self.assertIsInstance(cols[0]["type"], sqltypes.INTEGER)
        self.assertIsInstance(cols[1]["type"], sqltypes.TEXT)
        self.assertIsInstance(cols[2]["type"], D1DateTime)
        self.assertIsInstance(cols[3]["type"], D1Date)
        self.assertIsInstance(cols[4]["type"], D1Boolean)
        self.assertEqual(
            [c["autoincrement"] for c in cols],
            [True, False, False, False, False],
        )

    def test_zero_row_select_keeps_column_names(self):
        with self.engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT * FROM {self.table_name} WHERE 1=0")
            )
            self.assertEqual(list(result.keys()), COLUMN_NAMES)
            self.assertEqual(result.all(), [])

    def test_reflected_columns_return_python_values(self):
        table = Table(self.table_name, MetaData(), autoload_with=self.engine)

        with self.engine.connect() as conn:
            rows = conn.execute(select(table).order_by(table.c.id)).all()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].created_at, datetime(2026, 9, 21, 10, 0))
        self.assertEqual(rows[0].day, date(2026, 9, 21))
        self.assertIs(rows[0].active, True)
        self.assertEqual(rows[1].created_at, datetime(2026, 9, 22, 11, 30))
        self.assertIs(rows[1].active, False)

    def test_messy_date_values_do_not_raise(self):
        name = f"sqlalchemy_d1_test_messy_{self.suffix}"
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        f"CREATE TABLE {name} "
                        "(id INTEGER PRIMARY KEY, created_at DATETIME)"
                    )
                )
                conn.execute(
                    text(
                        f"INSERT INTO {name} (id, created_at) VALUES "
                        "(1, 1758448800), (2, ''), "
                        "(3, '09/21/2026'), (4, NULL)"
                    )
                )
            table = Table(name, MetaData(), autoload_with=self.engine)
            with self.engine.connect() as conn:
                rows = conn.execute(select(table).order_by(table.c.id)).all()

            self.assertIsInstance(table.c.created_at.type, D1DateTime)
            self.assertEqual(
                [r.created_at for r in rows],
                [1758448800, "", "09/21/2026", None],
            )
        finally:
            with self.engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {name}"))

    def test_cf_internal_tables_are_hidden(self):
        tables = inspect(self.engine).get_table_names()

        self.assertIn(self.table_name, tables)
        self.assertEqual([t for t in tables if t.startswith("_cf_")], [])

    def test_views_are_listed_and_reflected(self):
        inspector = inspect(self.engine)

        self.assertIn(self.view_name, inspector.get_view_names())
        self.assertNotIn(self.view_name, inspector.get_table_names())

        cols = inspector.get_columns(self.view_name)
        self.assertEqual(
            [c["name"] for c in cols], ["id", "name", "created_at"]
        )
        self.assertIsInstance(cols[2]["type"], D1DateTime)

    def test_cf_prefixed_view_is_refused_or_hidden(self):
        name = f"_cf_sqlalchemy_d1_test_{self.suffix}"
        with self.engine.connect() as conn:
            try:
                conn.execute(text(f"CREATE VIEW {name} AS SELECT 1 AS x"))
            except DBAPIError:
                return
            try:
                self.assertNotIn(name, inspect(self.engine).get_view_names())
            finally:
                conn.execute(text(f"DROP VIEW IF EXISTS {name}"))

    def test_create_all_round_trips_and_reflects_as_text(self):
        name = f"sqlalchemy_d1_test_created_{self.suffix}"
        metadata = MetaData()
        table = Table(
            name,
            metadata,
            Column("id", Integer, primary_key=True),
            Column("created_at", DateTime),
            Column("active", Boolean),
        )
        value = datetime(2026, 9, 21, 10, 30, 15)
        try:
            metadata.create_all(self.engine)
            with self.engine.begin() as conn:
                conn.execute(
                    table.insert(),
                    {"id": 1, "created_at": value, "active": True},
                )
            with self.engine.connect() as conn:
                row = conn.execute(select(table)).one()

            self.assertEqual(row.created_at, value)
            self.assertIs(row.active, True)

            cols = inspect(self.engine).get_columns(name)
            self.assertIsInstance(cols[1]["type"], sqltypes.TEXT)
            self.assertIsInstance(cols[2]["type"], sqltypes.INTEGER)
        finally:
            metadata.drop_all(self.engine)


if __name__ == "__main__":
    unittest.main()
