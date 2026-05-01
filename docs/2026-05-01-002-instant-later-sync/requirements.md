# Feature #2 — Natychmiastowy sync Later (outbox)

## Zakres

Po lokalnym dodaniu (`l`) lub usunięciu (`d`) filmu z listy Later, zmiana jest
niezawodnie propagowana do playlisty YouTube — także po wyłączeniu lub crashu
aplikacji. Mechanizm bazuje na trwałej kolejce operacji (outbox pattern) w
SQLite, dzięki czemu żadna lokalna zmiana nie jest tracona.

## Tabela `later_sync_queue`

```sql
CREATE TABLE later_sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('add', 'remove')),
    created_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    status TEXT NOT NULL DEFAULT 'pending'  -- pending / failed
);
CREATE INDEX idx_later_sync_queue_created ON later_sync_queue(created_at);
```

Migracja: `CREATE TABLE IF NOT EXISTS ...` przy starcie aplikacji. Brak migracji
danych — tabela jest nowa.

## Atomowość lokalnej zmiany

Toggle `l` / `d` wykonuje w **jednej transakcji SQLite**:

1. `UPDATE videos SET watch_later = ? WHERE id = ?`
2. `INSERT INTO later_sync_queue ...` (po deduplikacji — patrz niżej).

Jeśli proces padnie po commicie — kolejka jest spójna z bazą.

### Sprytna deduplikacja

Przed wstawieniem nowego wpisu sprawdzamy ostatni `pending` wpis dla tego
`video_id`:

- Jeśli ostatni wpis ma akcję **przeciwną** (np. `add` a teraz robimy `remove`):
  kasujemy ten ostatni wpis i nie wstawiamy nowego (`add` + `remove` = no-op
  względem stanu YouTube).
- Jeśli ostatni wpis ma **tę samą** akcję: nie wstawiamy duplikatu (idempotent).
- Jeśli brak `pending` wpisu: wstawiamy nowy.

Wpisy `failed` są **pomijane** w deduplikacji — zostają w tabeli aż do retry
przez użytkownika.

## Worker thread

- Daemon thread, startuje razem z TUI (z `__init__.py` lub `main.py` przy
  uruchomieniu TUI).
- Pętla:
  1. Pobiera najstarszy `pending` wpis (`ORDER BY created_at ASC LIMIT 1`).
  2. Wywołuje `YouTubeClient.add_to_playlist` lub `remove_from_playlist`
     (te same metody co istniejący `later_sync.py`).
  3. Po sukcesie: `DELETE FROM later_sync_queue WHERE id = ?`.
  4. Po błędzie: `attempts += 1`, zapisuje `last_error`. Jeśli
     `attempts >= 5`: ustawia `status = 'failed'`. W przeciwnym razie czeka
     wg backoffu i ponawia.
- Sygnalizacja nowych wpisów: `threading.Event` (`outbox_event`) — TUI ustawia
  event po `l`/`d`, worker `wait()` na nim między iteracjami.
- Brak `pending` wpisów → worker czeka na event (`wait()` bez timeoutu).
- Wszystkie błędy API logowane do `~/.cache/yt-sub/sync_error.log`
  (istniejący plik).

### Backoff

Lista opóźnień w sekundach: `[1, 5, 30, 300, 1800]`. Indeks = numer aktualnej
próby (0..4). Po piątej nieudanej próbie wpis przechodzi w `status='failed'`,
**bez dalszych retry** automatycznych. Suma maksymalnego oczekiwania ≈ 36 minut.

### Kolejność przy starcie aplikacji

1. Worker drenuje **outbox** (wszystkie `pending`).
2. Dopiero po opróżnieniu outboxa odpala się normalny dwukierunkowy
   `later_sync` (z `later_sync.py`).

Dzięki temu lokalne zmiany trafiają do YouTube przed reconciliacją, więc
two-way sync widzi spójny stan i nie odtwarza usuniętych pozycji.

## Feedback w UI

### Pasek statusu — wskaźnik `[E]rrors`

- Gdy w bazie istnieje `≥ 1` wpis ze `status='failed'`: w pasku statusu
  pokazywany jest segment `[E]rrors` jako **pierwsza pozycja** (przed
  `[q]uit`), z **czerwonym tłem** (nowy `curses` color pair, np. `bg=red,
  fg=default` z `A_REVERSE`).
- Wskaźnik znika automatycznie, gdy nie ma już `failed` wpisów (po retry/usunięciu).
- Status bar przelicza obecność failed entries przy każdym redraw (zapytanie
  SQL `SELECT COUNT(*) WHERE status='failed'` — tanie).

### Otwarcie aplikacji z zaległymi failed

Jeśli przy starcie outbox po pierwszym przejściu nadal zawiera wpisy `failed`
(z poprzedniej sesji): wskaźnik `[E]rrors` jest widoczny od razu po
narysowaniu paska statusu. **Bez popup-modala** — wystarczy wskaźnik.

### Klawisz `E` — Errors view (modal)

Otwiera modal z listą wpisów `failed`.

**Wiersz listy:**
```
<add/remove>   <tytuł filmu>   —   <kanał>   (<attempts> prób, <last_error skrócone>)
```

- Tytuł i kanał pobierane przez `JOIN` z tabelą `videos` po `video_id`.
- Jeśli filmu **nie ma** w lokalnej bazie: fallback do `video_id` jako tytułu,
  kanał pusty.
- `last_error` skrócony do np. 60 znaków z wielokropkiem.

**Skróty w modal:**

| Klawisz | Akcja |
|---------|-------|
| `j` / `k` / strzałki | Nawigacja po liście |
| `r` | Retry zaznaczonego wpisu — `attempts = 0`, `status = 'pending'`, sygnał `outbox_event.set()` |
| `R` | Retry wszystkich `failed` (jak `r` zastosowane do każdego) |
| `d` | Usuń wpis z kolejki (`DELETE FROM later_sync_queue`); lokalna flaga `watch_later` zostaje jak jest |
| `ESC` lub `E` | Zamknij modal i wróć do głównego widoku |

Modal zamyka się automatycznie, gdy lista jest pusta (np. po retry wszystkich
i ich powodzeniu).

## Help overlay

Nowy wpis: `E — Show failed Later sync errors`.

## Niefunkcjonalne

- Worker nie blokuje TUI nigdy — wszystkie API call w wątku tła, sleep podczas
  backoffu w worker thread (nie głównej pętli).
- Quit aplikacji (`q`) **nie czeka** na worker — daemon thread kończy się z
  procesem. Niezakończone `pending` wpisy zostają w bazie i są dograne przy
  następnym starcie.
- Brak limitów rozmiaru kolejki — w praktyce użytkownik nie wygeneruje setek
  zmian na minutę.

## Decyzje projektowe

- **Outbox vs. fire-and-forget**: wybrany outbox dla pełnej niezawodności
  (zmiana przeżyje crash, brak sieci, kill -9, restart maszyny).
- **Brak limitu rozmiaru kolejki**: ryzyko znikome (Later toggle to akcja
  ręczna), a limit dodaje złożoność.
- **5 prób z backoffem do 30min**: kompromis między odpornością na krótkie
  utraty sieci a feedbackiem do użytkownika w rozsądnym czasie.
- **`failed` wpisy zostają w bazie**: użytkownik decyduje, czy ponowić, czy
  porzucić. Nie tracimy informacji o tym, co miało się stać.
- **Modal Errors zamiast inline notyfikacji**: lista może być dłuższa, a
  użytkownik potrzebuje kontekstu (tytuł, kanał) do decyzji.
