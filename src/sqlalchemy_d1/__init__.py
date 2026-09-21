"""SQLAlchemy dialect for Cloudflare D1"""

from importlib.metadata import PackageNotFoundError, version

from sqlalchemy.dialects import registry

from .dialect import D1Dialect

try:
    __version__ = version("sqlalchemy-d1")
except PackageNotFoundError:
    # Running from a source tree or a vendored copy
    __version__ = "0+unknown"

__all__ = ["D1Dialect", "__version__"]

registry.register("d1", "sqlalchemy_d1.dialect", "D1Dialect")
