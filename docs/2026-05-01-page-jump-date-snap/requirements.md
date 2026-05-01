# Requirements — Przeskakiwanie z omijaniem nagłówków dat

## Zakres

Zmiana zachowania wszystkich poleceń nawigacyjnych, które przyjmują licznik
(`j`, `k`, `Ctrl+f`/PageDown, `Ctrl+b`/PageUp), tak aby:

1. Licznik oznaczał **linie ekranu** (każdy wiersz = 1 linia, włącznie z
   nagłówkami dat), a nie pozycje listy filmów.
2. Gdy obliczona pozycja docelowa wskazuje na nagłówek daty, kursor ląduje
   na **pierwszym filmie poniżej** tego nagłówka.

## Polecenia objęte zmianą

| Polecenie | Aktualnie | Po zmianie |
|---|---|---|
| `[n]j` / `KEY_DOWN` | Przeskakuje `n` filmów (daty nie liczą) | Przeskakuje `n` linii ekranu; jeśli cel = data → snap w przód |
| `[n]k` / `KEY_UP` | Przeskakuje `n` filmów (daty nie liczą) | Przeskakuje `n` linii ekranu; jeśli cel = data → snap w przód |
| `Ctrl+f` / PageDown | Cel = `curr + (sh-2)` linii; snap wstecz | Cel = `curr + (sh-2)` linii; snap w przód |
| `Ctrl+b` / PageUp | Cel = `curr - (sh-2)` linii; snap w przód | Bez zmian (już poprawne) |

## Polecenia NIE objęte zmianą

- `J` / `K` — skoki o N dni; semantycznie przeskakują grupy dat, nagłówek to
  cel, zachowanie poprawne.
- `gg` / `G` / `[n]G` — skoki do góry/dołu/linii; snap w przód już jest.
- `KEY_UP` / `KEY_DOWN` bez licznika (count=1) — pojedyncze kroki po filmach;
  pomijanie dat jest pożądane, bez zmian.

## Definicja „snap w przód"

Po wyliczeniu `target` (indeks w `display_items`):

```
for idx in range(target, len(display_items)):
    if display_items[idx]["type"] == "video":
        selected_id = display_items[idx]["content"].id
        break
```

Jeśli za nagłówkiem nie ma już żadnego filmu (koniec listy), kursor pozostaje
na aktualnej pozycji (brak zmiany `selected_id`).

## Decyzje projektowe

- **Snap w przód dla obu kierunków** (`j` i `k`): kursor zawsze trafia na
  pierwszy film poniżej nagłówka daty, niezależnie od kierunku skoku.
  Uzasadnienie: nagłówek daty jest separatorem grupy — pierwsza pozycja grupy
  jest naturalnym miejscem lądowania.
- **`j`/`k` bez licznika (count=1) bez zmian**: pojedynczy krok zawsze
  przechodzi do sąsiedniego filmu; wstawienie nagłówka jako etapu pośredniego
  byłoby dezorientujące.
- Pozycja widoku (`top_line`) po skoku pozostaje niezmieniona — istniejący
  mechanizm auto-scroll wystarczy.

## Kontekst techniczny

`display_items` to płaska lista `{"type": "header"|"video", "content": ...}`.
Każdy wpis zajmuje dokładnie jedną linię ekranu. Indeks w `display_items`
odpowiada bezpośrednio numerowi linii (od `top_line`).
