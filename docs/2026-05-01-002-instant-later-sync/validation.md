# Walidacja — Feature #2

## Scenariusze funkcjonalne (golden path)

### S1 — Dodanie filmu, sync online
1. Aplikacja online, lista YouTube Later istnieje.
2. Wybierz film, naciśnij `l`.
3. Sprawdź:
   - Lokalna flaga `watch_later = 1` w `videos`.
   - Wpis w `later_sync_queue` od razu znika po sukcesie API (worker drenuje
     w ciągu ~1s).
   - Film pojawia się w playliście YouTube (sprawdź w przeglądarce).
   - `[E]rrors` nie pojawia się w pasku statusu.

### S2 — Usunięcie filmu, sync online
1. Film dodany wcześniej do Later.
2. Naciśnij `d` w widoku Later.
3. Sprawdź jak w S1, ale dla `remove`.

### S3 — Deduplikacja `add` + `remove`
1. Aplikacja offline lub worker zatrzymany (np. utrata sieci).
2. Naciśnij `l`, potem `d` na tym samym filmie.
3. Sprawdź:
   - W `later_sync_queue` nie ma żadnego wpisu dla tego `video_id`
     (dedup wykasował poprzedni `add` przed wstawieniem `remove`).
   - Lokalna flaga `watch_later = 0`.

### S4 — Deduplikacja `add` + `add`
1. Naciśnij `l` na filmie.
2. Naciśnij `l` na tym samym filmie ponownie (gdy worker jeszcze nie zsync'ował).
3. Sprawdź: tylko jeden wpis `add` w kolejce.

## Scenariusze niezawodności

### S5 — Crash aplikacji z pending wpisem
1. Wyłącz internet.
2. Naciśnij `l` — wpis trafia do kolejki, worker zaczyna retry.
3. Zabij aplikację (`kill -9`) zanim minie pełny backoff.
4. Włącz internet, uruchom aplikację ponownie.
5. Sprawdź:
   - Worker przy starcie drenuje kolejkę.
   - Film pojawia się w YouTube Later.
   - Wpis znika z `later_sync_queue`.

### S6 — Trwały błąd API → failed
1. Symuluj trwały błąd (np. odebrane uprawnienia OAuth — testowo zmień scope w
   `credentials.pickle`, lub usuń playlist po stronie YouTube).
2. Naciśnij `l`.
3. Sprawdź:
   - Worker próbuje 5 razy z backoffem 1s/5s/30s/5min/30min.
   - Po 5 próbach wpis `status='failed'`, `last_error` wypełnione.
   - W pasku statusu pojawia się `[E]rrors` z czerwonym tłem jako
     pierwsza pozycja.

### S7 — Errors view: retry pojedynczy
1. Z S6: naciśnij `E`.
2. Sprawdź modal: tytuł filmu, kanał, action, attempts=5, last_error.
3. Napraw przyczynę błędu (włącz sieć / przywróć playlist).
4. Naciśnij `r` na zaznaczonym wpisie.
5. Sprawdź:
   - `attempts` resetuje się do 0, `status='pending'`.
   - Worker próbuje natychmiast (event set).
   - Po sukcesie wpis znika, modal sam się zamyka.
   - `[E]rrors` znika z paska statusu.

### S8 — Errors view: retry wszystkich (R)
1. Wymuś 2+ failed wpisy.
2. `E` → `R`.
3. Wszystkie failed → pending; worker drenuje.

### S9 — Errors view: usunięcie wpisu
1. Failed wpis dla filmu, którego nie chcesz już synchronizować.
2. `E` → `d` na zaznaczonym.
3. Sprawdź:
   - Wpis usunięty z kolejki.
   - Lokalna flaga `watch_later` **nie zmienia się**.
   - Modal pokazuje resztę listy (lub zamyka się, jeśli pusta).

### S10 — Otwarcie aplikacji z zaległymi failed
1. Zostaw aplikację z `failed` wpisami w bazie.
2. Wyłącz aplikację.
3. Uruchom ponownie.
4. Sprawdź:
   - Wskaźnik `[E]rrors` widoczny od razu po pierwszym narysowaniu paska
     statusu — bez popup-modala.
   - `E` otwiera modal z tymi samymi wpisami.

## Scenariusze spójności z istniejącym sync

### S11 — Outbox drenuje się przed two-way sync
1. W bazie 2 wpisy `pending` (np. po starcie aplikacji z poprzedniej sesji).
2. Uruchom aplikację.
3. Sprawdź w logach (lub przez print):
   - Outbox worker przetwarza wszystkie `pending`.
   - Dopiero potem startuje `later_sync` z `later_sync.py`.
   - Two-way sync widzi spójny stan i nie odtwarza pozycji usuniętych przez outbox.

### S12 — Two-way sync nie dodaje wpisów do outboxa
1. W playliście YouTube jest film, którego nie ma lokalnie z flagą `watch_later=1`.
2. Two-way sync ustawia flagę lokalnie.
3. Sprawdź: `later_sync_queue` jest pusty (sync użył `enqueue=False`).

## Wydajność i UI

### S13 — Status bar nie spowalnia rysowania
- `count_failed_ops()` musi być szybkie (count z indeksu lub bez join).
- Profilowanie: czas redraw przed/po dodaniu segmentu pomijalny (<1ms).

### S14 — Help overlay
- Naciśnij `?`. Sprawdź obecność wpisu `E — Show failed Later sync errors`.
- Wszystkie skróty mieszczą się w ramce.

### S15 — Quit nie czeka na worker
- Naciśnij `q` z pending wpisem w kolejce.
- Aplikacja zamyka się natychmiast.
- Pending wpis zostaje w bazie i jest dograny przy następnym starcie.

## Kryteria mergeable

- [ ] Wszystkie scenariusze S1–S15 przechodzą.
- [ ] Brak regresji w istniejących skrótach `l`/`d` (filtry, watch later view).
- [ ] Brak regresji w `later_sync.py` (start sync, dwukierunkowość).
- [ ] Type hints i docstrings (Google style) w nowych metodach.
- [ ] `pyproject.toml` bump wersji (MINOR).
- [ ] `SPECIFICATION.md` zaktualizowane.
- [ ] `TODO.md`: `#2` oznaczone jako `[x]`.
- [ ] Pliki `requirements.md`, `plan.md`, `validation.md` w katalogu feature
      i scommitowane.
