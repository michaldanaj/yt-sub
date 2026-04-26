
# Uruchamianie programu

Aplikacja jest spakowana jako pakiet `yt_sub` w `src/`. Do uruchomienia używaj uv:
```bash
uv run yt-sub
```
Albo jako moduł:
```bash
uv run python -m yt_sub
```

# Specyfikacja projektu

W pliku docs/SPECIFICATION.md znajduje się specyfikacja programu, którą przeważnie ty zarządzasz. Jeśli dodam jakieś wymaganie, doprecyzowanie jakiejś kwestii, po wykonaniu zadania dodaj odpowiednią aktualizację do specyfikacji. Specyfikacja powinna być tak napisana, że programista na jej podstawie odtworzy wszystkie funkcjonalności aplikacji.

# git

Jeśli poproszę o dokonanie jakiejś zmiany, zrób nową gałąź git, w której będziemy iterować aż do poprawnego rozwiązania. Po każdej modyfikacji kodu rób commit-a, żeby później łatwo można było wrócić do poprzednich wersji. Na koniec zapytaj mnie czy poprawki działają i jeśli uznam że modyfikacja jest poprawna, zrób merge do master z no-ff.

## Code Changes 

When fixing a bug or applying a change, audit ALL locations where the same pattern occurs — not just the first instance found. Check both panels, all views, and related display logic for the same issue.

 ## Code Style

This is a Python TUI application. Always use type hints and docstrings when writing or modifying functions. Follow existing code style conventions.

# Nowe funkcje

Każda nowa funkcja powinna zawierać typehint i szczegółowy docstring w formatowaniu google.

# Środowisko i ograniczenia

- Wszystkie komendy powłoki (bash), w tym `find`, `grep`, `ls`, MUSZĄ być uruchamiane wyłącznie wewnątrz bieżącego katalogu projektu.
- Nigdy nie używaj ścieżek bezwzględnych ani nie wychodź poza strukturę katalogów projektu (brak `..` i bezwzględnych ścieżek). Możesz nie rozpoczynać
  komend od cd do katalogu projektu. Claude jest wywoływany w katalogu projektu i nie ma potrzeby tam wchodzić.
- Jeśli potrzebujesz przeszukać coś poza projektem, najpierw zapytaj o zgodę.



