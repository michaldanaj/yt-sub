# Plan — #8 Odświeżenie zawartości (ręczna synchronizacja)

## Grupa 1: Refaktor `main.py` — wyodrębnienie `run_sync`

1. Przenieś logikę synchronizacji z wątku startowego do funkcji
   `run_sync(db, yt, config, sync_queue)`.
2. Wątek startowy wywołuje `run_sync(...)` — zachowanie bez zmian.

## Grupa 2: Wyzwalanie ręczne w `tui.py`

3. Dodaj do `YouTubeTUI.__init__` referencję do `db`, `yt`, `config`
   (sprawdź, czy już są dostępne lub wymaga to przekazania).
4. Dodaj atrybut `_sync_thread: threading.Thread | None`.
5. W `_handle_key` obsłuż `r` i `KEY_CTRL_R`:
   - Jeśli `_sync_thread` jest aktywny (`is_alive()`), ignoruj.
   - W przeciwnym razie utwórz i uruchom nowy wątek daemon z `run_sync`.
6. Zaktualizuj tabelę skrótów w ekranie pomocy (`?`).

## Grupa 3: Dokumentacja i testy

7. Zaktualizuj SPECIFICATION.md (nowy skrót `r`/`Ctrl+R` w tabeli klawiszy).
8. Oznacz #8 jako `[x]` w TODO.md.
