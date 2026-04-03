# Specyfikacja Techniczna: YouTube Subscription Monitor

## 1. Cel Aplikacji
Aplikacja służy do pobierania, przechowywania w lokalnej bazie danych i wyświetlania najnowszych filmów z kanałów subskrybowanych przez użytkownika na platformie YouTube. Umożliwia filtrowanie po dacie, przeglądanie szczegółów oraz odtwarzanie filmów w `mpv`.

## 2. Architektura i Technologie
- **Język:** Python 3.
- **Baza danych:** SQLite (`youtube_monitor.db`).
- **API:** YouTube Data API v3.
- **Autoryzacja:** OAuth 2.0 (Flow: Installed Application); token zapisywany w `credentials.pickle`.
- **Interfejs:** TUI (Terminal User Interface) oparty na `curses`.
- **Odtwarzacz:** Zewnętrzny odtwarzacz `mpv`.
- **Synchronizacja w tle:** Wątek daemon (`threading`) komunikujący się z TUI przez `queue.Queue`.

## 3. Struktura Projektu
- `main.py`: Punkt wejściowy, obsługa argumentów CLI i orkiestracja synchronizacji.
- `database.py`: Klasa `Database` zarządzająca schematem SQLite i operacjami zapisu/odczytu.
- `youtube_client.py`: Klasa `YouTubeClient` obsługująca API, autoryzację i równoległe pobieranie danych.
- `tui.py`: Klasa `YouTubeTUI` zarządzająca dwupanelowym interfejsem użytkownika.
- `models.py`: Definicje struktur danych (`Channel`, `Video`) z użyciem `dataclasses`.
- `config.json`: Opcjonalny plik konfiguracyjny (tworzony/edytowany przez użytkownika).
- `credentials.pickle`: Token OAuth 2.0 (tworzony automatycznie przy pierwszym uruchomieniu).
- `sync_error.log`: Log błędów synchronizacji w tle (tworzony automatycznie przy błędzie).

## 4. Przechowywanie Danych (SQLite)
Aplikacja przechowuje pełne informacje dostępne przez API:
- **Tabela `channels`**: ID, tytuł, opis, custom URL, data publikacji kanału, URL miniatury, statystyki (widoki, subskrypcje, liczba filmów), ID playlisty uploads, data ostatniego filmu (`latest_video_date`), surowy JSON.
- **Tabela `videos`**: ID, ID kanału, tytuł, opis, data publikacji, czas trwania (format `H:MM:SS` lub `M:SS` z prawostronnym wyrównaniem do 7 znaków), URL miniatury, statystyki (widoki, lajki, komentarze), tytuł kanału, status "Watch Later" (`watch_later`), data ostatniej synchronizacji (`last_synced`), surowy JSON.
- **Tabela `metadata`**: Przechowuje datę ostatniej synchronizacji (klucz `last_update`).

Schematy tabel są tworzone przy każdym uruchomieniu (`CREATE TABLE IF NOT EXISTS`). Istniejące bazy danych są migrowane przez `ALTER TABLE ADD COLUMN` dla brakujących kolumn (`watch_later`, `last_synced`).

## 5. Przepływ Logiczny i Synchronizacja

### 5.1. Synchronizacja Danych
1. Aplikacja uruchamia się natychmiast, wyświetlając filmy już obecne w bazie danych.
2. W tle (wątek daemon) uruchamiany jest proces synchronizacji:
   - Pobierz aktualną listę subskrypcji i zaktualizuj tabelę `channels`.
   - Pobierz statystyki kanałów z bazy (średnia dzienna liczba filmów z ostatnich 3 miesięcy).
   - Pobierz datę ostatniej synchronizacji z tabeli `metadata`.
   - Oblicz datę rozpoczęcia synchronizacji z 24-godzinnym "overlapem" (aby zaktualizować metadane niedawno opublikowanych filmów, np. czas trwania po zakończeniu streamu live).
   - Pobierz wszystkie nowe filmy od obliczonej daty, używając adaptacyjnej wielkości paczek (`maxResults`).
   - Zapisz nowe filmy w bazie danych używając `ON CONFLICT DO UPDATE`, co aktualizuje metadane (tytuł, czas trwania, statystyki, `last_synced`) i zachowuje status "Watch Later" (kolumna `watch_later` nie jest nadpisywana przy konflikcie).
   - Prześlij nowe filmy do działającego interfejsu TUI przez `sync_queue`.
   - Zaktualizuj datę ostatniej synchronizacji w `metadata`.
3. Błędy synchronizacji są logowane do `sync_error.log` (z pełnym traceback).

#### Adaptacyjna wielkość paczek
Dla każdego kanału `maxResults` obliczany jest wzorem:
```
max_results = max(round(avg_per_day * days_since_last_sync), 2)
max_results = min(max_results, 50)  # limit API
```
Jeśli kanał nie ma filmów w bazie (brak danych historycznych), używana jest wartość `10`. Domyślnie (bez historii) wartość wynosi `50`.

### 5.2. Interfejs TUI (Dual-Pane)

#### Lewy panel: Lista filmów
Filmy pogrupowane nagłówkami dat w formacie `--- YYYY-MM-DD ---`.

**Skróty klawiszowe:**
| Klawisz | Akcja |
|---------|-------|
| `j` / `k` / strzałki | Przesunięcie w dół / górę (można poprzedzić liczbą, np. `5j`) |
| `J` / `K` | Skok o jeden dzień w dół / w górę (można poprzedzić liczbą, np. `3J`) |
| `gg` | Skok na początek listy |
| `G` | Skok na koniec listy (lub `[n]G` — skok do konkretnej linii) |
| `zz` | Wycentrowanie widoku na aktualnie wybranym filmie |
| `Enter` | Odtworzenie wybranego filmu w `mpv` |
| `o` | Otwarcie wybranego filmu w domyślnej przeglądarce (`xdg-open`) |
| `y` | Skopiowanie URL wybranego filmu do schowka (`xclip` lub `wl-copy`) |
| `l` | Dodanie wybranego filmu do listy "Watch Later" |
| `L` | Przełączenie widoku na listę "Watch Later" / powrót |
| `d` | Usunięcie wybranego filmu z listy "Watch Later" |
| `s` | Przełączenie widoczności Shortów (filmów poniżej progu czasu) |
| `S` | Ustawienie progu czasu dla Shortów (w sekundach; zapisywane do `config.json`) |
| `b` | Przełączenie filtrowania tylko do filmów z aktualnego kanału |
| `/` | Wejście w tryb live search (filtrowanie po tytule lub nazwie kanału) |
| `PageUp` / `Ctrl+b` | Przewinięcie o pełną stronę w górę |
| `PageDown` / `Ctrl+f` | Przewinięcie o pełną stronę w dół |
| `?` | Wyświetlenie ekranu pomocy ze skrótami |
| `ESC` | Powrót do głównej listy i wyczyszczenie wszystkich filtrów (wyszukiwanie, kanał, "Watch Later") |
| `q` | Wyjście z aplikacji |

**Tryb live search (`/`):**
- Po wciśnięciu `/` interfejs wchodzi w tryb wyszukiwania.
- Wpisywany tekst filtruje listę w czasie rzeczywistym (filtrowanie po tytule i nazwie kanału).
- Pasek statusu wyświetla `SEARCH: <zapytanie>_`.
- `Enter` lub `ESC` kończy tryb wyszukiwania (filtr pozostaje aktywny po `Enter`, czyszczony przez `ESC` lub `ESC` z poziomu normalnego trybu).

**Numeracja linii:**
Względna numeracja (jak w Vim) — wyświetlana z lewej strony listy. Aktualnie zaznaczona linia pokazuje swój bezwzględny numer (1-based), pozostałe linie pokazują odległość od zaznaczenia.

**Kolorystyka:**
Konfigurowalne kolory (256-kolorowe) dla: nagłówka daty, kropki, czasu trwania, kanału, tytułu, tła zaznaczenia. Aktualne zaznaczenie oznaczone kolorową kropką (`•`) i podświetleniem tła.

#### Prawy panel: Szczegóły wybranego filmu
Wyświetla:
- Tytuł (pogrubiony, zawijany do szerokości panelu)
- Channel (nazwa kanału)
- Published (data i godzina publikacji)
- Synced (data ostatniej synchronizacji, o ile dostępna)
- Duration (czas trwania)
- Views (liczba wyświetleń z separatorami tysięcy)
- Likes (liczba lajków)
- Separator poziomy
- Opis filmu (zawijany, z zachowaniem pustych linii)
- **Miniatura** (na dole panelu, wycentrowana poziomo)

#### Miniatura
- Renderowana przez **Kitty Terminal Graphics Protocol** (natywna grafika, nie ASCII).
- Źródło: `maxresdefault.jpg` (1280×720) z fallbackiem do `thumbnail_url` z bazy.
- Pliki cache: `.thumb_cache/{video_id}_max.jpg`.
- Rozmiar: obraz przeskalowany w PIL do szerokości `cols * cell_w_px` px (dopasowany do panelu), bez sztucznego rozciągania.
- Pozycja: przypięty do dołu panelu; liczba wierszy obliczana przez `ceil(target_h_px / cell_h_px)` na podstawie faktycznego rozmiaru komórki z `TIOCGWINSZ`.
- Centrowanie poziome: offset = `(pane_width - img_cols) // 2`.
- Pre-download: podczas synchronizacji thumbnails pobierane są równolegle (10 wątków) dla wszystkich nowych filmów.

#### Pasek statusu (footer)
Zawsze widoczny na dole ekranu. Tryby wyświetlania:
- **Tryb normalny:** Przyciski skrótów (`[q]uit`, `[?] help`, `[/] find`, `[y]ank`, `[o]pen`, Watch Later, `[d]el`, Shorts, `[b]y channel`), aktualny filtr kanału oraz aktywne zapytanie wyszukiwania.
- **Tryb wyszukiwania:** `SEARCH: <zapytanie>_` (pogrubiony).
- **Synchronizacja w toku:** Dodatkowy segment `[SYNC: <wiadomość>]` z postępem.
- **Bufor wejścia (liczba przed komendą):** Segment `:<bufor>`.

Podczas synchronizacji progress komunikaty przesyłane są przez `sync_queue` i wyświetlane w pasku statusu. Po zakończeniu synchronizacji wyświetlany jest toast z informacją o liczbie zaktualizowanych/dodanych filmów.

#### Aktualizacja TUI po synchronizacji
Gdy wątek synchronizacji prześle nowe filmy:
1. Nowe filmy są scalane z istniejącą listą przez deduplikację po ID.
2. Przy aktualizacji istniejącego filmu zachowywany jest jego status `watch_later`.
3. Lista sortowana jest po `published_at` malejąco.
4. Zaznaczenie jest przywracane na ten sam film (po ID).
5. Wyświetlany jest toast z liczbą zaktualizowanych elementów.

## 6. Argumenty Wiersza Poleceń
| Argument | Opis |
|----------|------|
| `--date-limit YYYY-MM-DD` | Synchronizacja od podanej daty (zamiast daty z ostatniej synchronizacji) |
| `--display-channels` | Wyświetlenie listy kanałów z bazy danych (bez TUI) |
| `--no-tui` | Wyświetlenie 50 ostatnich filmów w trybie tekstowym (bez TUI, bez synchronizacji w tle) |
| `--sync-only` | Tylko synchronizacja danych, bez uruchamiania TUI |

## 7. Konfiguracja (`config.json`)
Użytkownik może personalizować wygląd TUI poprzez edycję pliku `config.json`. Plik tworzony jest automatycznie z wartościami domyślnymi przy ustawieniu progu Shortów przez `S`. Jeśli plik nie istnieje, używane są wartości domyślne.

Struktura:
```json
{
    "colors": {
        "header": 103,
        "dot": 210,
        "duration": 150,
        "channel": 117,
        "title": 231,
        "selected_bg": 238,
        "detail_label": 103,
        "detail_value": 231
    },
    "ui": {
        "pane_split_ratio": 0.5,
        "page_scroll_ratio": 0.8,
        "shorts_threshold_seconds": 90
    }
}
```
- `colors`: Kody 256-kolorowe dla poszczególnych elementów interfejsu.
- `pane_split_ratio`: Proporcja podziału ekranu (lewa/prawa); domyślnie `0.5` (50/50).
- `page_scroll_ratio`: Nieużywane bezpośrednio (PageUp/Down przewijają o `sh-2` linii).
- `shorts_threshold_seconds`: Próg czasu (w sekundach) dla filtrowania Shortów; domyślnie `90`.
