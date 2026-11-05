"""Use the standard TOML reader, or its offline fallback on Python 3.9/3.10."""

try:
    import tomllib
except ModuleNotFoundError:
    from ._vendor import tomli as tomllib

__all__ = ["tomllib"]
