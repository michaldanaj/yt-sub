#!/usr/bin/env bash
# Instaluje lub aktualizuje aplikację yt-sub jako narzędzie uv oraz
# rejestruje wpis w menu aplikacji (Desktop Entry).
#
# Uruchamiana z menu, aplikacja startuje w domyślnym terminalu
# użytkownika (wpis ma Terminal=true). Do poprawnego wyświetlania
# miniatur potrzebny jest terminal z obsługą Kitty Graphics Protocol
# (Kitty, Konsole, WezTerm, Ghostty itp.).
#
# Użycie:
#   ./install.sh            # instalacja lub aktualizacja
#   ./install.sh --remove   # odinstalowanie
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="yt-sub"
ICON_SRC="$SCRIPT_DIR/icons/$APP_NAME.svg"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_DST="$ICON_DIR/$APP_NAME.svg"
DESKTOP_SRC="$SCRIPT_DIR/$APP_NAME.desktop"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_DST="$DESKTOP_DIR/$APP_NAME.desktop"

refresh_caches() {
    command -v update-desktop-database &>/dev/null \
        && update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    command -v gtk-update-icon-cache &>/dev/null \
        && gtk-update-icon-cache -tq "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
}

# --- Odinstalowanie ---
if [[ "${1:-}" == "--remove" ]]; then
    echo "Odinstalowuję $APP_NAME..."
    uv tool uninstall "$APP_NAME" 2>/dev/null && echo "  Pakiet usunięty" \
        || echo "  Pakiet nie był zainstalowany"
    rm -f "$ICON_DST"    && echo "  Ikona usunięta"
    rm -f "$DESKTOP_DST" && echo "  Wpis .desktop usunięty"
    refresh_caches
    echo "Gotowe."
    exit 0
fi

# --- Sprawdź uv ---
if ! command -v uv &>/dev/null; then
    echo "Błąd: uv nie jest zainstalowane (https://docs.astral.sh/uv/)" >&2
    exit 1
fi

# --- Instalacja / aktualizacja pakietu ---
echo "Instaluję $APP_NAME..."
if uv tool list 2>/dev/null | grep -q "^$APP_NAME "; then
    uv tool install --reinstall "$SCRIPT_DIR"
    echo "  Zaktualizowano."
else
    uv tool install "$SCRIPT_DIR"
    echo "  Zainstalowano."
fi

# --- Ikona ---
mkdir -p "$ICON_DIR"
cp "$ICON_SRC" "$ICON_DST"
echo "  Ikona: $ICON_DST"

# --- Wpis .desktop ---
mkdir -p "$DESKTOP_DIR"
cp "$DESKTOP_SRC" "$DESKTOP_DST"
echo "  Desktop: $DESKTOP_DST"

# --- Odśwież cache pulpitu ---
refresh_caches

echo
echo "Gotowe. Uruchamianie:"
echo "  - z menu aplikacji: 'yt-sub'"
echo "  - z terminala:      $APP_NAME"
