import re
import unittest

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Time,
    cast,
    literal_column,
    select,
)
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import ArgumentError
from sqlalchemy.schema import CreateTable
from sqlalchemy_cloudflare_d1.dialect import (
    CloudflareD1Dialect,
    D1Boolean,
    D1Date,
    D1DateTime,
    D1Time,
)

from sqlalchemy_d1 import types as d1types
from sqlalchemy_d1.dialect import D1Dialect

SUPERSET_TEMPORAL = [
    re.compile(r"^timestamp", re.IGNORECASE),
    re.compile(r"^datetime", re.IGNORECASE),
    re.compile(r"^date", re.IGNORECASE),
    re.compile(r"^time", re.IGNORECASE),
]
SUPERSET_BOOLEAN = [re.compile(r"^bool(ean)?", re.IGNORECASE)]
SUPERSET_STRING = [re.compile(r"^(tiny|medium|long)?text", re.IGNORECASE)]


class DummySupersetColumnSpec:
    def __init__(self, dialect):
        self._dialect = dialect

    def type_string(self, sqla_type):
        return sqla_type.compile(dialect=self._dialect).upper()

    def matches(self, sqla_type, patterns):
        name = self.type_string(sqla_type)
        return any(p.match(name) for p in patterns)


class D1TypeCompilerTestSuite(unittest.TestCase):
    dialect = D1Dialect()
    upstream = CloudflareD1Dialect()

    def build_table(self, **kw):
        return Table(
            "events",
            MetaData(),
            Column("id", Integer, primary_key=True),
            Column("name", String(50)),
            Column("created_at", DateTime),
            Column("updated_at", TIMESTAMP),
            Column("day", Date),
            Column("at", Time),
            Column("active", Boolean),
            **kw,
        )

    def test_reflected_types_compile_to_declared_names(self):
        cases = [
            (d1types.DATETIME(), "DATETIME"),
            (d1types.TIMESTAMP(), "TIMESTAMP"),
            (d1types.DATE(), "DATE"),
            (d1types.TIME(), "TIME"),
            (d1types.BOOLEAN(), "BOOLEAN"),
        ]
        for sqla_type, expected in cases:
            self.assertEqual(sqla_type.compile(dialect=self.dialect), expected)
            self.assertEqual(str(sqla_type), expected)

    def test_reflected_types_compile_like_generic_types_elsewhere(self):
        cases = [
            (d1types.DATETIME(), DateTime()),
            (d1types.TIMESTAMP(), TIMESTAMP()),
            (d1types.DATE(), Date()),
            (d1types.TIME(), Time()),
            (d1types.BOOLEAN(), Boolean()),
        ]
        for other in [sqlite.dialect(), postgresql.dialect(), self.upstream]:
            for declared, generic in cases:
                self.assertEqual(
                    declared.compile(dialect=other),
                    generic.compile(dialect=other),
                )

    def test_generic_types_compile_like_upstream(self):
        for sqla_type in [
            Integer(),
            String(),
            String(50),
            DateTime(),
            TIMESTAMP(),
            Date(),
            Time(),
            Boolean(),
            D1DateTime(),
            D1Date(),
            D1Time(),
            D1Boolean(),
        ]:
            self.assertEqual(
                sqla_type.compile(dialect=self.dialect),
                sqla_type.compile(dialect=self.upstream),
            )

    def test_type_name_is_the_same_bare_and_in_create_table(self):
        table = Table(
            "events",
            MetaData(),
            Column("created_at", DateTime),
            Column("active", Boolean),
            Column("declared_at", d1types.DATETIME()),
            Column("declared_active", d1types.BOOLEAN()),
        )

        ddl = str(CreateTable(table).compile(dialect=self.dialect))

        for column in table.columns:
            bare = column.type.compile(dialect=self.dialect)
            self.assertIn(f"{column.name} {bare}", ddl)
        self.assertIn("created_at TEXT", ddl)
        self.assertIn("declared_at DATETIME", ddl)

    def test_superset_sees_dates_and_booleans(self):
        spec = DummySupersetColumnSpec(self.dialect)
        for declared in ["DATETIME", "TIMESTAMP", "DATE", "TIME"]:
            sqla_type = self.dialect._get_column_type(declared)
            self.assertTrue(spec.matches(sqla_type, SUPERSET_TEMPORAL))
            self.assertFalse(spec.matches(sqla_type, SUPERSET_STRING))
        for declared in ["BOOLEAN", "BOOL"]:
            sqla_type = self.dialect._get_column_type(declared)
            self.assertTrue(spec.matches(sqla_type, SUPERSET_BOOLEAN))

    def test_create_table_matches_upstream(self):
        table = self.build_table()

        ours = str(CreateTable(table).compile(dialect=self.dialect))
        theirs = str(CreateTable(table).compile(dialect=self.upstream))

        self.assertEqual(ours, theirs)
        self.assertNotIn("DATETIME", ours)
        self.assertNotIn("TIMESTAMP", ours)
        self.assertNotIn("BOOLEAN", ours)

    def test_create_strict_table_matches_upstream(self):
        try:
            table = self.build_table(sqlite_strict=True)
        except ArgumentError:
            self.skipTest("this SQLAlchemy has no sqlite_strict option")

        ours = str(CreateTable(table).compile(dialect=self.dialect))
        theirs = str(CreateTable(table).compile(dialect=self.upstream))

        self.assertEqual(ours, theirs)
        self.assertIn("STRICT", ours)
        self.assertNotIn("DATETIME", ours)
        self.assertNotIn("BOOLEAN", ours)

    def test_cast_matches_upstream(self):
        for sqla_type in [DateTime, Date, Boolean, Integer, String]:
            stmt = select(cast(literal_column("x"), sqla_type))
            self.assertEqual(
                str(stmt.compile(dialect=self.dialect)),
                str(stmt.compile(dialect=self.upstream)),
            )


if __name__ == "__main__":
    unittest.main()
