# Requirements — #8 Odświeżenie zawartości (ręczna synchronizacja)

## Cel

Użytkownik może ręcznie wyzwolić pełną synchronizację w trakcie działania
aplikacji bez konieczności restartu.

---

## Skrót klawiszowy

- `r` lub `Ctrl+R` — wyzwala sync.
- Jeśli sync już trwa (wątek w tle aktywny), naciśnięcie jest **ignorowane
  bez żadnego komunikatu**.

---

## Zakres synchronizacji

Identyczny jak sync przy starcie aplikacji:

1. Pobranie nowych filmów z kanałów od daty ostatniej synchronizacji
   (z 24h overlapem, adaptacyjny `maxResults`).
2. Two-way sync listy Later z YouTube (`later_sync.sync_later`).

Brak wariantu "od podanej daty" — tylko od ostatniej daty synchronizacji.

---

## Zachowanie TUI

- TUI pozostaje w pełni responsywne podczas syncu.
- Pasek statusu wyświetla postęp identycznie jak przy starcie (segmenty
  `[SYNC: <wiadomość>]`).
- Po zakończeniu syncu filmów wyświetlany jest toast z liczbą
  zaktualizowanych/dodanych filmów (jak przy starcie).
- Po zakończeniu Later sync wyświetlany jest komunikat (jak przy starcie).

---

## Zmiany w kodzie

### `main.py`

Wyodrębniona funkcja `run_sync(db, yt, config, sync_queue)` zawierająca
całą logikę synchronizacji (filmy + Later sync), wywoływana zarówno przy
starcie, jak i ręcznie przez `r`. Obecnie ta logika jest inline w wątku
startowym.

### `tui.py`

- Obsługa klawiszy `r` i `Ctrl+R` w `_handle_key`.
- Flaga `_sync_running: bool` (lub sprawdzanie przez `thread.is_alive()`)
  do detekcji czy sync już trwa.
- Przy wyzwoleniu: uruchomienie nowego wątku daemon z `run_sync`.

---

## Decyzje projektowe

- **Brak komunikatu przy podwójnym sync** — cicha ignoracja nie rozprasza.
- **Brak wariantu "od początku"** — specjalne zakresy obsługuje `--date-limit`
  z CLI.
- **Reużycie istniejącej kolejki** — `sync_queue` przekazywana jest do TUI
  przy inicjalizacji; ten sam mechanizm obsługuje wiadomości z ręcznego syncu.
