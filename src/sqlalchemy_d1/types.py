# sqlalchemy_d1/types.py
"""
Types that reflection returns for columns declared with a date or boolean
type name.

Each one behaves like the upstream D1 type it extends. On the d1 dialect it
compiles to its class name, which is the name the column was declared with.
Generic types such as DateTime are left to upstream.
"""

from sqlalchemy.ext.compiler import compiles
from sqlalchemy_cloudflare_d1.dialect import (
    D1Boolean,
    D1Date,
    D1DateTime,
    D1Time,
)


class DATETIME(D1DateTime):
    pass


class TIMESTAMP(D1DateTime):
    # Other dialects print TIMESTAMP too, as for sqlalchemy.TIMESTAMP
    __visit_name__ = "TIMESTAMP"


class DATE(D1Date):
    pass


class TIME(D1Time):
    pass


class BOOLEAN(D1Boolean):
    pass


# Other dialects compile these like the generic types they extend
@compiles(DATETIME, "d1")
@compiles(TIMESTAMP, "d1")
@compiles(DATE, "d1")
@compiles(TIME, "d1")
@compiles(BOOLEAN, "d1")
def compile_declared_name(type_, compiler, **kw):
    return type(type_).__name__
