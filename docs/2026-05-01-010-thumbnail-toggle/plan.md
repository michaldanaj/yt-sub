# Plan implementacji — Feature #10

## Grupa 1 — Konfiguracja i stan

1. W `TUI.__init__` dodaj `show_thumbnails` do domyślnego configa:
   `"ui": {..., "show_thumbnails": True}`.
2. Przy starcie odczytaj wartość: `self.show_thumbnails = self.config["ui"].get("show_thumbnails", True)`.
3. Metoda `_save_config()` (lub inline) — zapis `config.json` przy toggle.

## Grupa 2 — Obsługa klawisza `t`

1. W `_handle_key`: dodaj case `ord('t')`:
   - `self.show_thumbnails = not self.show_thumbnails`
   - `self.config["ui"]["show_thumbnails"] = self.show_thumbnails`
   - Zapis do `config.json`.
   - Jeśli wyłączono: `thumbnails.clear_kitty()`.
2. Dodaj `t` do listy skrótów w `_draw_help_overlay`.

## Grupa 3 — Warunkowe rysowanie thumbnailów

1. W głównej pętli rysowania, gdzie obliczane jest `thumb_rows`:
   - Jeśli `not self.show_thumbnails`: `thumb_rows = 0`.
2. Blok `if thumb_rows > 0 and thumb_video:` jest już warunkowy — brak zmian.
3. Przy `show_thumbnails = False` wywołaj `thumbnails.clear_kitty()` raz
   przy toggle (już w kroku 2).

## Grupa 4 — Status bar + dokumentacja

1. Dodaj wskaźnik stanu thumbnail do paska statusu.
2. Zaktualizuj `SPECIFICATION.md`.
3. Oznacz `#10` jako `[x]` w `TODO.md`.
