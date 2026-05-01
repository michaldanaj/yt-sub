# Plan — Synchronizacja listy Later z YouTube

## Grupa 1 — Gałąź i baza danych

1. Utwórz gałąź `feature-later-youtube-sync` z `master`.
2. Dodaj tabelę `later_sync_snapshot` do `database.py`:
   - `_create_tables()` — nowa instrukcja `CREATE TABLE IF NOT EXISTS`
   - `get_later_snapshot() -> dict[str, str]` — zwraca `{video_id: playlist_item_id}`
   - `save_later_snapshot(snapshot: dict[str, str]) -> None` — czyści i zapisuje

## Grupa 2 — Metody YouTube API

3. Dodaj do `youtube_client.py`:
   - `find_or_create_playlist(name: str) -> str`
   - `get_playlist_items(playlist_id: str) -> dict[str, str]`
   - `add_to_playlist(playlist_id: str, video_id: str) -> str`
   - `remove_from_playlist(playlist_item_id: str) -> None`

## Grupa 3 — Moduł `later_sync.py`

4. Utwórz `src/yt_sub/later_sync.py` z dataclassą `SyncResult` i funkcją
   `sync_later(db, yt, config) -> SyncResult`.
5. Zaimplementuj algorytm two-way sync z requirements.md.

## Grupa 4 — Konfiguracja

6. Zaktualizuj domyślny config w `tui.py` (`_load_config`) — dodaj sekcję
   `"youtube": {"later_playlist_name": "Later", "later_playlist_id": ""}`.
7. Zapis `later_playlist_id` do `config.json` po odnalezieniu/utworzeniu
   playlisty w `later_sync.py`.

## Grupa 5 — Integracja z TUI i `main.py`

8. W `tui.py`:
   - Obsługa wiadomości `{"type": "later_sync_done", ...}` w `_poll_sync_queue`
   - Wyświetlenie podsumowania w pasku statusu, odświeżenie `display_items`
9. W `main.py`: wywołanie `sync_later` w tle po starcie aplikacji.

## Grupa 6 — Walidacja i merge

11. Testy wg `validation.md`.
12. Po akceptacji: podbij MINOR (nowa funkcjonalność) w `pyproject.toml`,
    merge `--no-ff` do `master`.
