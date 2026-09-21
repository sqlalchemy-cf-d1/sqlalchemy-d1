# sqlalchemy_d1/types.py
"""
Types that reflection returns for columns declared with a date or boolean
type name.

Each one behaves like the upstream D1 type it extends, and compiles to its
class name, which is the name the column was declared with. Generic types
such as DateTime are left to upstream.
"""

from sqlalchemy_cloudflare_d1.dialect import (
    D1Boolean,
    D1Date,
    D1DateTime,
    D1Time,
)


# SQLAlchemy only picks up a __visit_name__ set in the class body itself
class DATETIME(D1DateTime):
    __visit_name__ = "d1_declared"


class TIMESTAMP(D1DateTime):
    __visit_name__ = "d1_declared"


class DATE(D1Date):
    __visit_name__ = "d1_declared"


class TIME(D1Time):
    __visit_name__ = "d1_declared"


class BOOLEAN(D1Boolean):
    __visit_name__ = "d1_declared"
