# Validation — #9 Zestawienie kanałów ze statystykami

## Warunki wstępne

Baza zawiera filmy z co najmniej 3 różnych kanałów, w tym filmy krótsze niż
próg Shorts i filmy z ostatnich 3 miesięcy.

---

## SC-1: Wejście i wyjście z widoku

1. Z głównej listy wciśnij `a`.
- **Oczekiwane:** Wyświetla się tabela z nagłówkiem i wierszami kanałów.
2. Wciśnij `ESC` (lub ponownie `a`).
- **Oczekiwane:** Powrót do głównej listy filmów bez zmian filtrów.

## SC-2: Nawigacja po wierszach

1. Wejdź w widok (`a`), wciśnij `j` kilka razy.
- **Oczekiwane:** Zaznaczenie przesuwa się w dół; przy ostatnim wierszu
  nie wychodzi poza listę.
2. Wciśnij `k`.
- **Oczekiwane:** Zaznaczenie cofa się w górę.

## SC-3: Sortowanie

1. Wciśnij `2` (Avg/mo).
- **Oczekiwane:** Tabela sortuje się rosnąco po `Avg/mo`; nagłówek kolumny 2
  pokazuje `▲`.
2. Wciśnij `2` ponownie.
- **Oczekiwane:** Kierunek odwrócony (`▼`), malejąco.
3. Wciśnij `1`.
- **Oczekiwane:** Sortowanie po nazwie kanału rosnąco (`▲`).

## SC-4: Zmiana okresu (`m`)

1. Wciśnij `m`, wpisz `6`, zatwierdź Enter.
- **Oczekiwane:** Statystyki przeliczone za 6 miesięcy; pasek statusu pokazuje
  `period: 6mo`; `stats_months: 6` zapisane w `config.json`.
2. Wciśnij `m`, wpisz `0` lub `25`, zatwierdź.
- **Oczekiwane:** Wartość odrzucona (poza zakresem 1–24); okres bez zmian.

## SC-5: Enter — przejście do listy kanału

1. Zaznacz wiersz kanału X, wciśnij Enter.
- **Oczekiwane:** Powrót do głównej listy z filtrem ustawionym na kanał X
  (tylko filmy tego kanału widoczne).

## SC-6: Kanał bez filmów w okresie

1. Ustaw okres na 1 miesiąc; kanał który dawno nie publikował.
- **Oczekiwane:** Wiersz tego kanału pokazuje `0.0` / `0.0` / `—`.

## SC-7: Skrót w helperze

1. Z głównego widoku wciśnij `?`.
- **Oczekiwane:** Tabela skrótów zawiera `a` z opisem.
