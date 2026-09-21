import sqlite3
import unittest

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    Table,
    create_engine,
    inspect,
    text,
    types as sqltypes,
)
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable

from sqlalchemy_d1 import types as d1types

SCHEMA = [
    "CREATE TABLE events ("
    "id INTEGER PRIMARY KEY, name TEXT DEFAULT 'anonymous', "
    "created_at DATETIME, updated_at TIMESTAMP, day DATE, at TIME, "
    "is_active BOOLEAN NOT NULL DEFAULT 1, price DECIMAL(10,2))",
    "CREATE TABLE lowercase_key (id integer PRIMARY KEY, name TEXT)",
    "CREATE TABLE composite_key "
    "(a INTEGER, b INTEGER, c TEXT, PRIMARY KEY (b, a))",
    "CREATE TABLE text_key (code TEXT PRIMARY KEY, amount INTEGER)",
    "CREATE TABLE int_key (id INT PRIMARY KEY, name TEXT)",
    "CREATE TABLE bigint_key (id BIGINT PRIMARY KEY, name TEXT)",
    "CREATE TABLE without_rowid "
    "(id INTEGER PRIMARY KEY, name TEXT) WITHOUT ROWID",
    "CREATE TABLE strict_without_rowid "
    "(id INTEGER PRIMARY KEY, name TEXT) STRICT, WITHOUT ROWID",
    "CREATE VIEW event_names AS SELECT id, name, created_at FROM events",
]


class D1ReflectionTestSuite(unittest.TestCase):
    """
    Runs reflection against an in-memory SQLite database. It answers
    PRAGMA and sqlite_master queries the same way D1 does.
    """

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "d1://acct:tok@dbid",
            creator=lambda: sqlite3.connect(":memory:"),
            poolclass=StaticPool,
        )
        cls.addClassCleanup(cls.engine.dispose)
        with cls.engine.begin() as conn:
            for statement in SCHEMA:
                conn.execute(text(statement))

    def autoincrement(self, table_name):
        cols = inspect(self.engine).get_columns(table_name)
        return [c["autoincrement"] for c in cols]

    def test_get_columns_reflects_types_and_autoincrement(self):
        cols = inspect(self.engine).get_columns("events")

        self.assertEqual(
            [c["name"] for c in cols],
            [
                "id",
                "name",
                "created_at",
                "updated_at",
                "day",
                "at",
                "is_active",
                "price",
            ],
        )
        self.assertEqual(
            [type(c["type"]) for c in cols],
            [
                sqltypes.INTEGER,
                sqltypes.TEXT,
                d1types.DATETIME,
                d1types.TIMESTAMP,
                d1types.DATE,
                d1types.TIME,
                d1types.BOOLEAN,
                sqltypes.DECIMAL,
            ],
        )
        self.assertEqual(
            [c["primary_key"] for c in cols], [True] + [False] * 7
        )
        self.assertEqual(
            [c["autoincrement"] for c in cols], [True] + [False] * 7
        )
        self.assertTrue(cols[1]["nullable"])
        self.assertFalse(cols[6]["nullable"])
        self.assertEqual(cols[1]["default"], "'anonymous'")

    def test_autoincrement_ignores_case_of_integer(self):
        self.assertEqual(self.autoincrement("lowercase_key"), [True, False])

    def test_autoincrement_false_for_composite_primary_key(self):
        self.assertEqual(
            self.autoincrement("composite_key"), [False, False, False]
        )

    def test_autoincrement_false_for_text_primary_key(self):
        self.assertEqual(self.autoincrement("text_key"), [False, False])

    def test_autoincrement_false_unless_declared_as_integer(self):
        # Only INTEGER makes the column an alias for the rowid
        self.assertEqual(self.autoincrement("int_key"), [False, False])
        self.assertEqual(self.autoincrement("bigint_key"), [False, False])

    def test_autoincrement_false_without_rowid(self):
        self.assertEqual(self.autoincrement("without_rowid"), [False, False])
        self.assertEqual(
            self.autoincrement("strict_without_rowid"), [False, False]
        )

    def test_get_pk_constraint_keeps_key_order(self):
        inspector = inspect(self.engine)

        self.assertEqual(
            inspector.get_pk_constraint("composite_key"),
            {"constrained_columns": ["b", "a"], "name": None},
        )
        self.assertEqual(
            inspector.get_pk_constraint("events")["constrained_columns"],
            ["id"],
        )
        self.assertEqual(
            inspector.get_pk_constraint("event_names")["constrained_columns"],
            [],
        )

        table = Table("composite_key", MetaData(), autoload_with=self.engine)
        self.assertEqual([c.name for c in table.primary_key], ["b", "a"])

    def test_views_are_listed_and_reflected(self):
        inspector = inspect(self.engine)

        self.assertEqual(inspector.get_view_names(), ["event_names"])
        self.assertNotIn("event_names", inspector.get_table_names())

        cols = inspector.get_columns("event_names")
        self.assertEqual(
            [c["name"] for c in cols], ["id", "name", "created_at"]
        )
        self.assertIsInstance(cols[2]["type"], d1types.DATETIME)
        self.assertEqual(
            [c["autoincrement"] for c in cols], [False, False, False]
        )

    def test_get_view_definition_returns_create_statement(self):
        definition = inspect(self.engine).get_view_definition("event_names")

        self.assertEqual(
            definition,
            "CREATE VIEW event_names AS "
            "SELECT id, name, created_at FROM events",
        )

    def test_get_view_definition_raises_for_missing_view(self):
        inspector = inspect(self.engine)

        with self.assertRaises(NoSuchTableError):
            inspector.get_view_definition("missing")
        with self.assertRaises(NoSuchTableError):
            inspector.get_view_definition("events")

    def test_has_table_finds_tables_and_views(self):
        inspector = inspect(self.engine)

        self.assertTrue(inspector.has_table("events"))
        self.assertTrue(inspector.has_table("event_names"))
        self.assertFalse(inspector.has_table("missing"))

    def test_create_all_skips_a_name_taken_by_a_view(self):
        metadata = MetaData()
        Table("event_names", metadata, Column("id", Integer, primary_key=True))

        # Would fail with "view event_names already exists" otherwise
        metadata.create_all(self.engine)

        self.assertIn("event_names", inspect(self.engine).get_view_names())

    def test_table_comment_and_check_constraints_are_empty(self):
        inspector = inspect(self.engine)

        self.assertEqual(inspector.get_table_comment("events"), {"text": None})
        self.assertEqual(inspector.get_check_constraints("events"), [])

    def test_reflected_table_is_recreated_with_declared_types(self):
        table = Table("events", MetaData(), autoload_with=self.engine)

        ddl = str(CreateTable(table).compile(dialect=self.engine.dialect))

        for column_ddl in [
            "created_at DATETIME",
            "updated_at TIMESTAMP",
            "day DATE",
            "at TIME",
            "is_active BOOLEAN",
        ]:
            self.assertIn(column_ddl, ddl)


if __name__ == "__main__":
    unittest.main()
