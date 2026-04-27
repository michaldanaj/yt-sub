"""yt-sub: TUI for browsing YouTube subscriptions."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version


def _resolve_version() -> str:
    """Returns the installed package version, falling back to ``0.0.0+dev``.

    ``importlib.metadata.version`` only succeeds when the project has been
    installed (``uv tool install`` or ``uv sync`` of the local package). When
    running straight from a checkout via ``python src/yt_sub/__main__.py``,
    no metadata is registered and we return a dev sentinel instead of crashing.
    """
    try:
        return _pkg_version("yt-sub")
    except PackageNotFoundError:
        return "0.0.0+dev"


__version__ = _resolve_version()
