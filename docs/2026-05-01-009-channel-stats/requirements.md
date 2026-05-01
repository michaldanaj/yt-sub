# Requirements — #9 Zestawienie kanałów ze statystykami

## Cel

Osobny widok tabelaryczny wyświetlający statystyki wszystkich kanałów z bazy
danych. Pozwala szybko ocenić aktywność kanałów i nawigować do listy filmów
wybranego kanału.

---

## Nawigacja

| Klawisz | Akcja |
|---------|-------|
| `a` | Wejście w widok statystyk (z głównej listy filmów) |
| `ESC` / `a` | Powrót do głównej listy filmów |
| `j` / `k` / strzałki | Ruch w górę/dół po wierszach tabeli |
| `1` / `2` / `3` / `4` | Sortowanie po kolumnie 1–4; ponowne wciśnięcie tej samej cyfry odwraca kierunek (asc ↔ desc) |
| `m` | Prompt zmiany okresu statystyk (`Months (1-24):`) |
| `Enter` | Powrót do głównej listy z filtrem wybranego kanału (`b`) |
| `q` | Wyjście z aplikacji |

---

## Kolumny tabeli

| # | Nagłówek | Zawartość |
|---|----------|-----------|
| 1 | `Channel` | Nazwa kanału (obcięta do dostępnej szerokości) |
| 2 | `Avg/mo` | Średnia liczba wszystkich filmów na miesiąc w zadanym okresie |
| 3 | `Non-short/mo` | Średnia liczba filmów niebędących shortami na miesiąc |
| 4 | `Median dur` | Mediana czasu trwania filmów niebędących shortami (format `M:SS` / `H:MM:SS`, wyrównana do prawej) |

Shorty definiowane są przez `shorts_threshold_seconds` z `config.json`
(ten sam próg co w głównym widoku).

---

## Obliczenia statystyk

Okres analizy: ostatnie `N` miesięcy wstecz od bieżącej daty (domyślnie 3).
Dolna granica: `today - N * 30 dni` (przybliżenie miesiąca).

- **Avg/mo**: `count(wszystkie filmy w okresie) / N`
- **Non-short/mo**: `count(filmy z duration_seconds >= threshold w okresie) / N`
- **Median dur**: mediana `duration_seconds` spośród filmów niebędących shortami
  w okresie; wyświetlana w formacie `H:MM:SS` / `M:SS` (wyrównana do prawej,
  7 znaków — identycznie jak pole `duration` w modelu `Video`).

Kanały bez filmów w zadanym okresie wyświetlają `0` / `0` / `—`.

---

## Konfiguracja

Nowy klucz w sekcji `"ui"` pliku `config.json`:

```json
"ui": {
    ...
    "stats_months": 3
}
```

- Domyślna wartość: `3`.
- Klawisz `m` wyświetla mini-prompt (jak istniejący prompt `S` dla Shorts
  threshold), waliduje zakres `1–24` i zapisuje do `config.json`.

---

## Sortowanie

- Domyślne: po kolumnie 1 (`Channel`), rosnąco (A→Z).
- Naciśnięcie `1`–`4` ustawia sortowanie na daną kolumnę rosnąco.
- Ponowne naciśnięcie tej samej cyfry odwraca kierunek.
- Wskaźnik kierunku (`▲`/`▼`) wyświetlany w nagłówku aktywnej kolumny.

---

## Wygląd

```
 #  Channel              Avg/mo  Non-short/mo  Median dur
────────────────────────────────────────────────────────
  1 Fireship               12.3           8.1     8:42
  2 ThePrimeagen            4.0           4.0    42:15
  ...
[a] back  [m] period: 3mo  [1-4] sort  [Enter] filter
```

- Nagłówki kolumn wyrównane do kolumn danych.
- Liczby wyrównane do prawej, `Median dur` wyrównana do prawej.
- Aktywny wiersz podświetlony (`A_REVERSE`), bez dodatkowych kolorów.
- Pasek statusu na dole: skróty + aktualny okres.

---

## Zmiany w kodzie

### `database.py`

Nowa metoda `get_channel_stats_table(months: int, threshold_seconds: int) -> list[ChannelStatRow]`
zwracająca listę dataclass z polami:
- `channel_id: str`
- `channel_title: str`
- `avg_per_month: float`
- `avg_non_short_per_month: float`
- `median_duration_seconds: float | None`

### `channel_stats.py` (nowy moduł)

Klasa `ChannelStatsView` z całą logiką rysowania tabeli i obsługi klawiszy
dla tego widoku. Analogicznie do wydzielenia `thumbnails.py` i `actions.py`
z `tui.py`.

### `tui.py`

`YouTubeTUI._handle_key` obsługuje `a` — importuje `ChannelStatsView`
i wywołuje `ChannelStatsView(...).run(stdscr)`. Po powrocie ewentualnie
ustawia `filter_channel_id`.

---

## Decyzje projektowe

- **Obliczenia w `database.py`** — dane są już w SQLite, prosta agregacja
  bez dodatkowych zapytań API.
- **Mediana w Pythonie** — SQLite nie ma wbudowanej funkcji `MEDIAN`;
  obliczana przez `statistics.median` po pobraniu listy wartości.
- **Osobna klasa widoku** — izoluje logikę rysowania tabeli od głównego TUI,
  co ułatwia przyszłe rozszerzenia (np. widok szczegółów kanału #4).
- **`N * 30 dni`** — uproszczenie zamiast prawdziwych miesięcy kalendarzowych;
  spójne i przewidywalne niezależnie od miesiąca uruchomienia.
