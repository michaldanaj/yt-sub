#!/usr/bin/env bash
# Instaluje lub aktualizuje aplikację yt-sub jako narzędzie uv oraz
# rejestruje wpis w menu aplikacji (Desktop Entry).
#
# Z menu aplikacja jest uruchamiana w nowym oknie WezTerm (terminal
# z obsługą Kitty Graphics Protocol, wymaganego do miniatur).
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

# XDG dirs (pakiet używa ich do config / bazy / cache).
XDG_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$APP_NAME"
XDG_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_NAME"

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

# --- Sprawdź zależności ---
if ! command -v uv &>/dev/null; then
    echo "Błąd: uv nie jest zainstalowane (https://docs.astral.sh/uv/)" >&2
    exit 1
fi
if ! command -v wezterm &>/dev/null; then
    echo "Ostrzeżenie: wezterm nie znalezione w PATH. Wpis .desktop go" >&2
    echo "  wymaga, więc uruchomienie z menu nie zadziała dopóki nie" >&2
    echo "  zainstalujesz WezTerm (https://wezfurlong.org/wezterm/)." >&2
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

# --- Migracja istniejących plików konfiguracji do XDG ---
# Tylko gdy plik źródłowy istnieje w katalogu projektu, a docelowy w XDG
# jeszcze nie. To zachowuje twoją działającą bazę i token OAuth przy
# pierwszej instalacji desktopowej.
mkdir -p "$XDG_CONFIG_DIR" "$XDG_DATA_DIR"
migrate() {
    local src="$1" dst="$2"
    if [[ -e "$src" && ! -e "$dst" ]]; then
        cp -p "$src" "$dst"
        echo "  Skopiowano: $(basename "$src") → $dst"
    fi
}
migrate "$SCRIPT_DIR/config.json"        "$XDG_CONFIG_DIR/config.json"
migrate "$SCRIPT_DIR/credentials.pickle" "$XDG_CONFIG_DIR/credentials.pickle"
for cs in "$SCRIPT_DIR"/client_secret_*.json; do
    [[ -e "$cs" ]] && migrate "$cs" "$XDG_CONFIG_DIR/$(basename "$cs")"
done
migrate "$SCRIPT_DIR/youtube_monitor.db" "$XDG_DATA_DIR/youtube_monitor.db"

# --- Wpis .desktop ---
# Wstaw pełną ścieżkę do binarki yt-sub, żeby launcher menu nie zależał
# od tego, czy ~/.local/bin jest w PATH środowiska Desktop Entry.
YT_SUB_BIN="$(command -v yt-sub || echo "$HOME/.local/bin/yt-sub")"
mkdir -p "$DESKTOP_DIR"
sed "s|@YT_SUB_BIN@|$YT_SUB_BIN|g" "$DESKTOP_SRC" > "$DESKTOP_DST"
echo "  Desktop: $DESKTOP_DST (Exec → $YT_SUB_BIN)"

# --- Odśwież cache pulpitu ---
refresh_caches

echo
echo "Gotowe. Uruchamianie:"
echo "  - z menu aplikacji: 'yt-sub'"
echo "  - z terminala:      $APP_NAME"
