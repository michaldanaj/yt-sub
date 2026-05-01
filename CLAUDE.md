
# Uruchamianie programu

Aplikacja jest spakowana jako pakiet `yt_sub` w `src/`. Do uruchomienia używaj uv:
```bash
uv run yt-sub
```
Albo jako moduł:
```bash
uv run python -m yt_sub
```

Po instalacji desktopowej (`./install.sh`) komenda `yt-sub` jest dostępna globalnie z `~/.local/bin/`, a aplikacja pojawia się w menu systemowym jako uruchamiana w domyślnym terminalu.

# Specyfikacja projektu

W pliku docs/SPECIFICATION.md znajduje się specyfikacja programu, którą przeważnie ty zarządzasz. Jeśli dodam jakieś wymaganie, doprecyzowanie jakiejś kwestii, po wykonaniu zadania dodaj odpowiednią aktualizację do specyfikacji. Specyfikacja powinna być tak napisana, że programista na jej podstawie odtworzy wszystkie funkcjonalności aplikacji.

# Worflow pracy

Jeśli pracujemy nad nowym feature, kroki taki:

* Stworzenie specyfikacji pod feature (patrz Nowy feature poniżej)
* Akceptacja specyfikacji przez człowieka
* Wykonanie implementacji

# Nowy feature

W doc/TODO.py są nowe funkcjonalności do implementacji. Znajdź specyfikację w tym pliku przy implementacji nowej. Zrób gałąź git, pytaj mnie o specyfikację
feature.

Stwórz:

- Nowy katalog YYYY-MM-DD-feature-name w docs/ dla prac nad tym feature
- W tym katalogu:
    - `plan.md` seria ponumerowanych grup zadań
    - `requirements.md` dla zakresu, decyzji i kotekstu
    - `validation.md` aby określić czy implementacja jest poprawna i można
      zrobić merge

Odnieś się do docs/SPECIFICATION.md, oraz istniejących specyfikaji feature'ów dla wskazówek.

Ważne: _musisz_ używać narzędzia AskUserQuestions,
zanim zapiszesz na dysk.

# git

Jeśli poproszę o dokonanie jakiejś zmiany, zrób nową gałąź git, w której będziemy iterować aż do poprawnego rozwiązania. Po każdej modyfikacji kodu rób commit-a, żeby później łatwo można było wrócić do poprzednich wersji. Na koniec zapytaj mnie czy poprawki działają i jeśli uznam że modyfikacja jest poprawna, podbij numer wersji programu w pyproject.toml i zrób merge do master z no-ff.

## Numeracja wersji (semver)

Wersja w `pyproject.toml` ma format `MAJOR.MINOR.PATCH`:
- **PATCH** (ostatnia cyfra) — poprawki błędów, refaktoryzacje wewnętrzne, drobne poprawki bez zmiany zachowania widocznego dla użytkownika.
- **MINOR** (środkowa cyfra) — nowa funkcjonalność dodana w sposób kompatybilny wstecz; zerujemy PATCH.
- **MAJOR** (pierwsza cyfra) — zmiany niekompatybilne wstecz (zmiana CLI, formatu danych, struktury katalogów XDG itp.); zerujemy MINOR i PATCH.

Domyślnie po zaakceptowanej zmianie podbijamy PATCH. MINOR/MAJOR podbijam tylko po Twoim potwierdzeniu lub gdy charakter zmiany jest jednoznaczny.

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



