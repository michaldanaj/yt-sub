# Plan implementacji — Feature #2

## Grupa 1 — Schemat bazy i metody DAO

1. W `database.py`:
   - W `Database._create_tables` (lub odpowiedniku) dodaj
     `CREATE TABLE IF NOT EXISTS later_sync_queue ...` + index na `created_at`.
   - Nowe metody:
     - `enqueue_later_op(video_id: str, action: Literal['add','remove']) -> None`
       — wykonuje deduplikację i insert w **jednej transakcji** wraz z
       `update_watch_later`.
     - `get_next_pending_op() -> Optional[QueueRow]` — najstarszy `pending`.
     - `mark_op_failed_attempt(op_id: int, error: str) -> int` — inkrementuje
       `attempts`, zwraca nową wartość; jeśli `>= 5` → `status='failed'`.
     - `delete_op(op_id: int) -> None`.
     - `get_failed_ops() -> List[QueueRow]` — z join do `videos` (tytuł,
       kanał, fallback do `video_id`).
     - `count_failed_ops() -> int` — szybki count.
     - `retry_op(op_id: int) -> None` — `attempts=0, status='pending', last_error=NULL`.
     - `retry_all_failed() -> int` — masowo, zwraca liczbę ponowionych.

2. Zmodyfikuj istniejący `update_watch_later`: zamiast tylko UPDATE,
   przyjmuje opcjonalny parametr `enqueue: bool = True` i wykonuje obie
   operacje atomowo (transakcja). Jeśli `enqueue=False`, zachowuje stare
   zachowanie (używane przez sync, który już nie powinien zaśmiecać outboxa).

## Grupa 2 — Worker thread

1. Nowy moduł `src/yt_sub/later_outbox.py`:
   - Klasa `LaterOutboxWorker`:
     - `__init__(db, youtube_client, outbox_event: threading.Event)`.
     - `start() -> None` — uruchamia daemon thread.
     - `stop() -> None` — opcjonalne, ustawia flagę zatrzymania
       (na potrzeby testów; w runtime polega na daemon).
     - `_run()` — pętla:
       - Pobiera `pending` op.
       - Brak op → `outbox_event.wait()`, `outbox_event.clear()`, kontynuuj.
       - Jest op: wywołaj API odpowiednio dla `add`/`remove`.
       - Sukces → `delete_op`.
       - Błąd → `mark_op_failed_attempt`; jeśli `attempts < 5` → `time.sleep(backoff[attempts-1])`; jeśli `>= 5` → kontynuuj do następnego.
   - Stała `BACKOFF_SECONDS = [1, 5, 30, 300, 1800]`.

2. W `main.py` (lub gdzie tworzony jest `YouTubeTUI`):
   - Utwórz `outbox_event = threading.Event()`.
   - Utwórz `LaterOutboxWorker` i wywołaj `.start()` przed startem TUI.
   - Przekaż `outbox_event` do TUI.

3. Kolejność przy starcie:
   - Worker startuje → drenuje `pending` (jeśli są).
   - **Po** drenażu (lub równolegle, ale z barierą) — startuje normalny
     `later_sync` z `later_sync.py`.
   - Najprostszy sposób: bariera = `event` ustawiany przez worker po pierwszym
     pełnym przejściu pętli (`outbox empty`). Sync czeka na ten event.

## Grupa 3 — Integracja z TUI: l/d

1. W `tui.py`, `_handle_key`:
   - `ord('l')`: po `db.update_watch_later(v.id, True)` zamiast osobnego call,
     wywołaj `db.update_watch_later_with_enqueue(v.id, True, action='add')`
     (lub przekaż `enqueue=True` do istniejącej metody).
   - `ord('d')`: analogicznie z `action='remove'`.
   - Po enqueue: `self.outbox_event.set()` żeby worker natychmiast się obudził.

## Grupa 4 — Status bar: wskaźnik `[E]rrors`

1. Nowy color pair (np. `pair 10`): `(default, RED)` → z `A_REVERSE` daje
   `(RED, default)`. Zdefiniowany w `_init_colors`.
2. W `_draw_status_bar`:
   - Na początku (przed `[q]uit`) sprawdź `db.count_failed_ops()`.
   - Jeśli `> 0`: dodaj segment `[E]rrors` z `curses.color_pair(10) | curses.A_REVERSE`.
   - Po nim normalny separator.

## Grupa 5 — Errors view (modal)

1. Nowa metoda `_draw_errors_view(stdscr)` w `tui.py` — analogicznie do
   `_draw_help_overlay`, ale z listą i własną pętlą obsługi klawiszy.
2. Render listy:
   - Pobierz `db.get_failed_ops()`.
   - Format wiersza: `{action:6} {title[:40]:42} — {channel[:20]:22} ({attempts} prób, {error[:60]})`.
   - Highlight wybranego wiersza (`A_REVERSE`).
3. Pętla klawiszy w modal:
   - `j`/`k`/strzałki: nawigacja.
   - `r`: `db.retry_op`, `outbox_event.set()`, refresh listy.
   - `R`: `db.retry_all_failed`, `outbox_event.set()`, refresh listy.
   - `d`: `db.delete_op`, refresh listy.
   - `ESC` lub `E`: zamknij.
4. Auto-zamknięcie: jeśli po refresh lista jest pusta, wracamy do głównego widoku.
5. Klawisz `E` w `_handle_key` głównej pętli: wywołuje `_draw_errors_view`.

## Grupa 6 — Help overlay

1. Dodaj wpis `("E", "Show failed Later sync errors")` do listy
   `shortcuts` w `_draw_help_overlay`.
2. Zwiększ `h` (wysokość) o 1 (z 23 do 24).

## Grupa 7 — Modyfikacja `later_sync.py`

1. Dwukierunkowy sync nie powinien zapisywać do `later_sync_queue` — używa
   `update_watch_later(..., enqueue=False)`.
2. Sync czeka na flagę gotowości outbox workera (`outbox_drained_event`).

## Grupa 8 — Dokumentacja i finalizacja

1. Aktualizacja `docs/SPECIFICATION.md`:
   - Sekcja o tabeli `later_sync_queue`.
   - Sekcja o worker thread i kolejności startu.
   - Skrót `E` w tabeli skrótów.
   - Wskaźnik `[E]rrors` w opisie paska statusu.
2. Oznacz `#2` jako `[x]` w `docs/TODO.md`.
3. Bump wersji w `pyproject.toml` (MINOR — nowa funkcja, kompatybilna wstecz).
