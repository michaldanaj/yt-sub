# Walidacja — Feature #19

## Kryteria akceptacji

### Nawigacja podstawowa
- [x] `j`/`k`/strzałki przesuwają o 1 wiersz.
- [ ] `5j` przesuwa o 5 wierszy w dół.
- [ ] `10k` przesuwa o 10 wierszy w górę.
- [x] Na krawędziach listy nie wychodzi poza zakres.

### gg / G / [n]G
- [ ] `gg` skacze na początek listy (`_selected = 0`).
- [x] `G` skacze na koniec listy.
- [ ] `5G` skacze do wiersza 5 (1-based); jeśli lista ma < 5 wierszy — na koniec.

### PageUp / PageDown
- [x] `PageUp` / `Ctrl+b` przewija o pełną stronę w górę.
- [x] `PageDown` / `Ctrl+f` przewija o pełną stronę w dół.

### zz
- [ ] `zz` centruje widok na zaznaczonym wierszu.

### Sortowanie `h`/`l`/`←`/`→`
- [x] `l` i `→` przełączają do następnej kolumny (cyklicznie: 0→1→2→3→0).
- [x] `h` i `←` przełączają do poprzedniej kolumny (cyklicznie: 0→3→2→1→0).
- [ ] `spacja` odwraca kierunek sortowania aktywnej kolumny.
- [x] Klawisze `1`–`4` NIE sortują już.

### Live search
- [x] `/` wchodzi w tryb wyszukiwania (status bar pokazuje `SEARCH: _`).
- [x] Wpisanie liter filtruje listę po nazwie kanału.
- [x] `Backspace` usuwa ostatni znak zapytania.
- [x] `Enter` wychodzi z trybu, filtr pozostaje aktywny.
- [x] `ESC` wychodzi z trybu i czyści filtr.
- [x] `j`/`k` w trybie wyszukiwania wpisują litery do zapytania (nie nawigują); strzałki nawigują.

### Brak regresji
- [x] `m` i `S` nadal działają (zmiana okresu / progu Shorts).
- [x] `Enter` zwraca `channel_id` (filtr kanału w TUI).
- [x] `a`/`ESC` wraca do głównego widoku.
- [ ] `q` kończy aplikację.
