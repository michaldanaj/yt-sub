# Validation — #8 Odświeżenie zawartości (ręczna synchronizacja)

## Warunki wstępne

- Aplikacja uruchomiona, sync startowy zakończony.
- Baza zawiera filmy, Later sync skonfigurowany.

---

## SC-1: Podstawowe wyzwolenie (`r`)

1. Uruchom aplikację, poczekaj na zakończenie syncu startowego.
2. Wciśnij `r`.
- **Oczekiwane:** Pasek statusu pokazuje `[SYNC: ...]`. Po zakończeniu
  wyświetla toast z liczbą zaktualizowanych filmów i komunikat o Later sync.

## SC-2: Podstawowe wyzwolenie (`Ctrl+R`)

1. Jak SC-1, ale wciśnij `Ctrl+R`.
- **Oczekiwane:** Identyczne zachowanie jak przy `r`.

## SC-3: Ignorowanie podwójnego sync

1. Wciśnij `r`, natychmiast wciśnij `r` ponownie zanim sync się skończy.
- **Oczekiwane:** Drugi `r` nie uruchamia dodatkowego wątku. Brak komunikatu.
  Pasek statusu pokazuje postęp jednego syncu.

## SC-4: TUI responsywne podczas syncu

1. Wciśnij `r`.
2. Podczas trwającego syncu nawiguj po liście (`j`/`k`), otwieraj filmy (`o`).
- **Oczekiwane:** Wszystkie akcje działają normalnie. Brak zawieszenia.

## SC-5: Nowe filmy pojawiają się po ręcznym syncu

1. Dodaj nowy film do kanału (lub cofnij datę ostatniej synchronizacji w DB).
2. Wciśnij `r`.
- **Oczekiwane:** Nowy film pojawia się na liście po zakończeniu syncu.

## SC-6: Skrót widoczny w ekranie pomocy

1. Wciśnij `?`.
- **Oczekiwane:** Tabela skrótów zawiera `r` / `Ctrl+R` z opisem.
