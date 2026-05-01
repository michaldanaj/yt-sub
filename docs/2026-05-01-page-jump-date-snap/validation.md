# Validation — Przeskakiwanie z omijaniem nagłówków dat

## Warunki wstępne

Lista zawiera filmy z nagłówkami dat po drodze, np.:
```
--- 2025-04-30 ---
Film A
Film B
--- 2025-04-29 ---
Film C
Film D
--- 2025-04-28 ---
Film E
```

## Scenariusze

### SC-1: `j` z licznikiem ląduje na filmie
- Ustaw kursor na Film A (linia 1).
- Wciśnij `2j`.
- Oczekiwany wynik: kursor na Film C (linia 3, pominięto nagłówek jako linię 2).

### SC-2: `j` z licznikiem ląduje dokładnie na dacie
- Ustaw kursor na Film A (linia 1).
- Wciśnij `3j`.
- Oczekiwany wynik: kursor na Film C (pierwszy film po nagłówku z linii 4).
  _Nie_ na Film D.

### SC-3: `k` z licznikiem ląduje dokładnie na dacie
- Ustaw kursor na Film C (linia 3).
- Wciśnij `2k`.
- Oczekiwany wynik: kursor na Film A (linia 1, bo linia −1 = nagłówek, snap w przód = Film A).
  Alternatywnie (jeśli snap w przód od nagłówka to Film C): kursor wraca na Film C.
  **Uwaga**: snap zawsze w przód, więc od nagłówka 2025-04-30 (linia 0) → Film A.

### SC-4: `k` bez licznika (count=1) — bez zmian
- Ustaw kursor na Film C.
- Wciśnij `k`.
- Oczekiwany wynik: kursor na Film B (pominięto nagłówek między nimi).

### SC-5: `j` bez licznika (count=1) — bez zmian
- Ustaw kursor na Film B.
- Wciśnij `j`.
- Oczekiwany wynik: kursor na Film C (pominięto nagłówek między nimi).

### SC-6: PAGE DOWN ląduje na nagłówku daty
- Ustaw kursor blisko początku listy.
- Wciśnij `Ctrl+f` (Page Down).
- Oczekiwany wynik: kursor na pierwszym filmie po nagłówku daty na pozycji
  `curr + (wysokość_ekranu - 2)`. Nie na ostatnim filmie przed nagłówkiem.

### SC-7: PAGE UP — bez zmian (już działa)
- Wciśnij `Ctrl+b` (Page Up) gdy kursor jest w środku listy.
- Oczekiwany wynik: kursor na pierwszym filmie po nagłówku daty na pozycji
  `curr - (wysokość_ekranu - 2)` (zachowanie jak przed zmianą).

### SC-8: Koniec listy — brak filmów za nagłówkiem
- Jeśli ostatni element to nagłówek (edge case).
- Oczekiwany wynik: kursor nie zmienia pozycji.
