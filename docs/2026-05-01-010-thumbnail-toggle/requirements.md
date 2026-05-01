# Feature #10 — Thumbnail jako opcja

## Zakres

Możliwość ukrycia thumbnailów w widoku szczegółów (prawy panel) za pomocą
klawisza skrótu oraz opcji w `config.json`.

## Wymagania

### Klawisz skrótu

| Klawisz | Akcja |
|---------|-------|
| `t` | Toggle widoczności thumbnailów (włącz/wyłącz) |

- Stan jest persystowany w `config.json` (klucz `ui.show_thumbnails`).
- Po toggle natychmiastowe przerysowanie: gdy ukrywamy — `thumbnails.clear_kitty()`,
  gdy pokazujemy — normalny redraw z thumbnailem.

### Konfiguracja

Nowy klucz w sekcji `"ui"` pliku `config.json`:

```json
"ui": {
    "show_thumbnails": true
}
```

Domyślna wartość: `true` (zachowanie identyczne z obecnym).

### Zachowanie przy wyłączonych thumbnailach

- `thumb_rows = 0` — prawy panel wypełnia całą wysokość bez rezerwy na obraz.
- `thumbnails.clear_kitty()` wywoływane przy wyłączaniu oraz przy każdym
  normalnym clear (brak regresji dla terminali bez Kitty).
- Pasek statusu odzwierciedla stan (np. `[t] thumb: on/off`).

## Decyzje projektowe

- Stan przechowywany w `self.config["ui"]["show_thumbnails"]` (bool).
- Zapis do `config.json` przy każdym toggle (jak `shorts_threshold_seconds`).
- Klucz `t` dodany do ekranu pomocy (`?`).
