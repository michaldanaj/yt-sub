"""Resolves filesystem paths used by the application.

When yt-sub is launched from a desktop entry the working directory is
the user's home, not the project root, so paths must be absolute and
follow the XDG Base Directory spec.

Layout:
- Config (``$XDG_CONFIG_HOME/yt-sub`` or ``~/.config/yt-sub``):
  ``config.json``, ``credentials.pickle``, ``client_secret_*.json``
- Data (``$XDG_DATA_HOME/yt-sub`` or ``~/.local/share/yt-sub``):
  ``youtube_monitor.db``
- Cache (``$XDG_CACHE_HOME/yt-sub`` or ``~/.cache/yt-sub``):
  ``.thumb_cache/``, ``sync_error.log``

Each resolver creates the parent directory on access so callers do not
need to ``mkdir -p`` themselves.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Optional

APP_NAME = "yt-sub"


def _xdg(env_var: str, default_subdir: str) -> Path:
    """Returns ``$ENV_VAR/yt-sub`` or ``$HOME/<default_subdir>/yt-sub``.

    Args:
        env_var: Name of the XDG environment variable (e.g. ``XDG_CONFIG_HOME``).
        default_subdir: Fallback directory under ``$HOME`` when the
            environment variable is unset (e.g. ``.config``).

    Returns:
        Absolute :class:`Path` to the application-specific directory.
        The directory is *not* created here; use :func:`_ensure` for that.
    """
    base = os.environ.get(env_var)
    if not base:
        base = os.path.join(os.path.expanduser("~"), default_subdir)
    return Path(base) / APP_NAME


def _ensure(path: Path) -> Path:
    """Creates ``path`` (as a directory) if missing and returns it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    """Returns the config directory, creating it if necessary."""
    return _ensure(_xdg("XDG_CONFIG_HOME", ".config"))


def data_dir() -> Path:
    """Returns the data directory, creating it if necessary."""
    return _ensure(_xdg("XDG_DATA_HOME", ".local/share"))


def cache_dir() -> Path:
    """Returns the cache directory, creating it if necessary."""
    return _ensure(_xdg("XDG_CACHE_HOME", ".cache"))


def config_file() -> Path:
    """Path to ``config.json`` (may not exist yet)."""
    return config_dir() / "config.json"


def credentials_file() -> Path:
    """Path to the OAuth token cache (may not exist yet)."""
    return config_dir() / "credentials.pickle"


def client_secret_file() -> Optional[Path]:
    """Locates the OAuth client-secret JSON.

    The filename depends on the Google Cloud client ID, so we glob for
    ``client_secret_*.json`` rather than hard-coding it.

    Returns:
        Path to the first matching file, or ``None`` if none exists.
    """
    matches = sorted(glob.glob(str(config_dir() / "client_secret_*.json")))
    return Path(matches[0]) if matches else None


def database_file() -> Path:
    """Path to the SQLite database (may not exist yet)."""
    return data_dir() / "youtube_monitor.db"


def thumb_cache_dir() -> Path:
    """Path to the thumbnail cache directory, creating it if necessary."""
    return _ensure(cache_dir() / "thumb_cache")


def log_file() -> Path:
    """Path to the sync error log (may not exist yet)."""
    return cache_dir() / "sync_error.log"
