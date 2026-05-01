# Feature #19 — Nawigacja i wyszukiwanie w widoku statystyk

## Zakres

Przenieść do `ChannelsStatsView` obsługę klawiszy nawigacyjnych i wyszukiwania
analogiczną do tej w głównej liście filmów (`tui.py`).

## Wymagania

### Nawigacja

| Klawisz | Akcja |
|---------|-------|
| `j` / `k` / strzałki | Przesunięcie w dół / górę |
| `[n]j` / `[n]k` | Przeskok o N wierszy (prefix numeryczny) |
| `gg` | Skok na początek listy |
| `G` | Skok na koniec listy |
| `[n]G` | Skok do wiersza N (1-based) |
| `PageUp` / `Ctrl+b` | Przewinięcie o pełną stronę w górę |
| `PageDown` / `Ctrl+f` | Przewinięcie o pełną stronę w dół |
| `zz` | Wycentrowanie widoku na zaznaczonym wierszu |

Prefix numeryczny (`[n]`) — cyfry wpisane przed `j`/`k`/`G` składają się
na licznik. Bufor jest czyszczony po każdej akcji.

### Sortowanie kolumn — zmiana skrótu

Dotychczasowe klawisze `1`–`4` kolidują z prefixem numerycznym.
Nowe skróty sortowania:

| Klawisz | Akcja |
|---------|-------|
| `h` lub `←` | Przełącz sortowanie na poprzednią kolumnę |
| `l` lub `→` | Przełącz sortowanie na następną kolumnę |
| Ponowne naciśnięcie na tej samej kolumnie | Odwraca kierunek sortowania |

Klawisze `1`–`4` zostają usunięte jako skróty sortowania.

### Wyszukiwanie live (`/`)

- Wciśnięcie `/` wchodzi w tryb wyszukiwania.
- Wpisywany tekst filtruje listę w czasie rzeczywistym po **nazwie kanału**
  (case-insensitive, substring).
- Pasek statusu pokazuje `SEARCH: <zapytanie>_`.
- Strzałki góra/dół działają w trybie wyszukiwania (nawigacja po wynikach).
- `Enter` kończy tryb wyszukiwania (filtr pozostaje aktywny).
- `ESC` kończy tryb wyszukiwania i czyści filtr, wracając do pełnej listy.

### Zachowanie po posortowaniu / przeładowaniu

Po zmianie sortowania (`h`/`l`/`←`/`→`) bufor numeryczny i filtr wyszukiwania
są resetowane; zaznaczenie i `_top_line` idą do 0.

## Decyzje projektowe

- Prefix numeryczny: bufor `_input_buffer` zbierający cyfry, czyszczony po
  każdej akcji nie-cyfrowej (analogicznie do `tui.py`).
- Sortowanie `h`/`l`/`←`/`→`: `h`/`←` przesuwa `_sort_col` w lewo (mod 4), `l`/`→` w prawo
  (mod 4). Jeśli nowa kolumna == stara, odwraca `_sort_asc`.
- Koalescencja trzymanego klawisza — **nie** wymagana w tym feature.
- Wyszukiwanie filtruje wiersze **po posortowaniu**.
- Status bar: zaktualizować skróty (usunąć `[1-4] sort`, dodać `[h/l/←/→] sort`,
  dodać `[/] search`).

## Kontekst

Podjęte odpowiedzi użytkownika:
- Wyszukiwanie: tylko nazwa kanału.
- Nawigacja: [n]j/[n]k, gg/G/[n]G, PageUp/PageDown, prefix numeryczny, zz.
- Sortowanie: `<`/`>` (prev/next kolumna), zamiast `1`–`4`.
