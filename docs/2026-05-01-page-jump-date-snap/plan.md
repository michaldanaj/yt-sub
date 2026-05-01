# Plan — Przeskakiwanie z omijaniem nagłówków dat

## Grupa 1 — Gałąź i przygotowanie

1. Utwórz gałąź `fix-page-jump-date-snap` z `master`.

## Grupa 2 — Implementacja w `src/yt_sub/tui.py`, metoda `_handle_key`

2. **`j` / KEY_DOWN z licznikiem** (linia ~719):
   Zamień pętlę liczącą filmy na:
   ```python
   target = min(len(self.display_items) - 1, curr + count)
   for idx in range(target, len(self.display_items)):
       if self.display_items[idx]["type"] == "video":
           self.selected_id = self.display_items[idx]["content"].id; break
   ```

3. **`k` / KEY_UP z licznikiem** (linia ~709):
   Zamień pętlę liczącą filmy na:
   ```python
   target = max(0, curr - count)
   for idx in range(target, len(self.display_items)):
       if self.display_items[idx]["type"] == "video":
           self.selected_id = self.display_items[idx]["content"].id; break
   ```

4. **PAGE DOWN / Ctrl+f** (linia ~791):
   Zmień kierunek przeszukiwania z wstecznego na wprzód:
   ```python
   for idx in range(target, len(self.display_items)):
       if self.display_items[idx]["type"] == "video":
           self.selected_id = self.display_items[idx]["content"].id; break
   ```

5. Commit po każdej zmianie.

## Grupa 3 — Walidacja i merge

6. Ręczne testy wg `validation.md`.
7. Po akceptacji: podbić PATCH w `pyproject.toml`, merge `--no-ff` do `master`.
