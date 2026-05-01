# Plan implementacji — Feature #19

## Grupa 1 — Prefix numeryczny + gg/G/[n]G

1. Dodaj atrybuty `_input_buffer: str = ""` i `_last_key: int = 0` do `__init__`.
2. W pętli `run()`: jeśli klawisz to cyfra, dołącz do `_input_buffer`, ustaw
   `_last_key`, kontynuuj pętlę (nie czyść bufora).
3. Przed każdą akcją: `count = int(_input_buffer) if _input_buffer else 1`,
   potem wyczyść `_input_buffer`.
4. `[n]j` / `[n]k`: `_selected ± count`, clamp do zakresu.
5. `gg` (double-key): jeśli `_last_key == ord('g')` i teraz `g` →
   `_selected = 0`.
6. `[n]G`: jeśli `_input_buffer` → skocz do wiersza `count - 1` (1-based);
   bez bufora → `_selected = len(rows) - 1`.
7. Wywołaj `_ensure_visible` po każdej zmianie `_selected`.

## Grupa 2 — PageUp / PageDown / zz

1. `PageUp` / `Ctrl+b` (key `2`): `_selected -= page_size`, clamp do 0.
2. `PageDown` / `Ctrl+f` (key `6`): `_selected += page_size`, clamp do max.
3. `page_size = sh - 3` (identycznie jak `visible` w `_draw`).
4. `zz`: `_top_line = _selected - page_size // 2`, clamp do `[0, max_top]`.

## Grupa 3 — Zmiana sortowania na `h`/`l`

1. Usuń obsługę `ord('1')`–`ord('4')` z `run()`.
2. Dodaj obsługę `ord('h')`, `ord('l')`, `curses.KEY_LEFT`, `curses.KEY_RIGHT`:
   - `l` / `KEY_RIGHT`: `new_col = (self._sort_col + 1) % 4`
   - `h` / `KEY_LEFT`: `new_col = (self._sort_col - 1) % 4`
   - Jeśli `new_col == self._sort_col`: `self._sort_asc = not self._sort_asc`
   - W przeciwnym razie: `_sort_col = new_col`, `_sort_asc = True`.
3. Po zmianie sortowania: `_selected = 0`, `_top_line = 0`,
   wyczyść `_input_buffer` i `_search_query`.

## Grupa 4 — Live search `/`

1. Dodaj atrybuty `_is_searching: bool = False` i `_search_query: str = ""`.
2. Klawisz `/` → `_is_searching = True`.
3. W trybie wyszukiwania (`_is_searching`):
   - Znaki drukowane (`32 <= key <= 126`): dołącz do `_search_query`.
   - `Backspace` (`curses.KEY_BACKSPACE`, `127`, `8`): usuń ostatni znak.
   - `Enter` (`10`, `13`): `_is_searching = False`.
   - `ESC` (`27`): `_is_searching = False`, `_search_query = ""`.
   - Strzałki / `j` / `k`: nawigacja normalna.
4. Metoda `_filtered_rows(rows) -> List[ChannelStatRow]`: filtruje po
   `_search_query.lower()` w `row.channel_title.lower()`.
5. W `run()`: `rows = self._filtered_rows(self._sorted_rows())`.
6. `_draw`: pasek statusu — jeśli `_is_searching`, pokaż `SEARCH: <q>_`;
   w przeciwnym razie normalny status z `[</>] sort  [/] search`.

## Grupa 5 — Status bar + dokumentacja

1. Zaktualizuj `_draw`: status bar z nowymi skrótami.
2. Zaktualizuj `SPECIFICATION.md` — sekcja skrótów widoku statystyk.
3. Oznacz `#19` jako `[x]` w `TODO.md`.
