# Walidacja — Feature #19

## Kryteria akceptacji

### Nawigacja podstawowa
- [ ] `j`/`k`/strzałki przesuwają o 1 wiersz.
- [ ] `5j` przesuwa o 5 wierszy w dół.
- [ ] `10k` przesuwa o 10 wierszy w górę.
- [ ] Na krawędziach listy nie wychodzi poza zakres.

### gg / G / [n]G
- [ ] `gg` skacze na początek listy (`_selected = 0`).
- [ ] `G` skacze na koniec listy.
- [ ] `5G` skacze do wiersza 5 (1-based); jeśli lista ma < 5 wierszy — na koniec.

### PageUp / PageDown
- [ ] `PageUp` / `Ctrl+b` przewija o pełną stronę w górę.
- [ ] `PageDown` / `Ctrl+f` przewija o pełną stronę w dół.

### zz
- [ ] `zz` centruje widok na zaznaczonym wierszu.

### Sortowanie `h`/`l`/`←`/`→`
- [ ] `l` i `→` przełączają do następnej kolumny (cyklicznie: 0→1→2→3→0).
- [ ] `h` i `←` przełączają do poprzedniej kolumny (cyklicznie: 0→3→2→1→0).
- [ ] Ponowne naciśnięcie na tej samej kolumnie odwraca kierunek sortowania.
- [ ] Klawisze `1`–`4` NIE sortują już.

### Live search
- [ ] `/` wchodzi w tryb wyszukiwania (status bar pokazuje `SEARCH: _`).
- [ ] Wpisanie liter filtruje listę po nazwie kanału.
- [ ] `Backspace` usuwa ostatni znak zapytania.
- [ ] `Enter` wychodzi z trybu, filtr pozostaje aktywny.
- [ ] `ESC` wychodzi z trybu i czyści filtr.
- [ ] Nawigacja `j`/`k` działa w trybie wyszukiwania.

### Brak regresji
- [ ] `m` i `S` nadal działają (zmiana okresu / progu Shorts).
- [ ] `Enter` zwraca `channel_id` (filtr kanału w TUI).
- [ ] `a`/`ESC` wraca do głównego widoku.
- [ ] `q` kończy aplikację.
