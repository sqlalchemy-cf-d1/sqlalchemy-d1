"""SQLAlchemy dialect for Cloudflare D1"""

from importlib.metadata import version

from sqlalchemy.dialects import registry

from .dialect import D1Dialect

__version__ = version("sqlalchemy-d1")
__all__ = ["D1Dialect", "__version__"]

registry.register("d1", "sqlalchemy_d1.dialect", "D1Dialect")
