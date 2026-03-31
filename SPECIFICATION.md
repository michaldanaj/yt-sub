# Specyfikacja Techniczna: YouTube Subscription Monitor

## 1. Cel Aplikacji
Aplikacja służy do pobierania, przechowywania w lokalnej bazie danych i wyświetlania najnowszych filmów z kanałów subskrybowanych przez użytkownika na platformie YouTube. Umożliwia filtrowanie po dacie, przeglądanie szczegółów oraz odtwarzanie filmów w `mpv`.

## 2. Architektura i Technologie
- **Język:** Python 3.
- **Baza danych:** SQLite (`youtube_monitor.db`).
- **API:** YouTube Data API v3.
- **Autoryzacja:** OAuth 2.0 (Flow: Installed Application).
- **Interfejs:** TUI (Terminal User Interface) oparty na `curses`.
- **Odtwarzacz:** Zewnętrzny odtwarzacz `mpv`.

## 3. Struktura Projektu
- `main.py`: Punkt wejściowy, obsługa argumentów i orkiestracja synchronizacji.
- `database.py`: Klasa `Database` zarządzająca schematem SQLite i operacjami zapisu/odczytu.
- `youtube_client.py`: Klasa `YouTubeClient` obsługująca API, autoryzację i równoległe pobieranie danych.
- `tui.py`: Klasa `YouTubeTUI` zarządzająca dwupanelowym interfejsem użytkownika.
- `models.py`: Definicje struktur danych (`Channel`, `Video`) z użyciem `dataclasses`.

## 4. Przechowywanie Danych (SQLite)
Aplikacja przechowuje pełne informacje dostępne przez API:
- **Tabela `channels`**: ID, tytuł, opis, URL, data publikacji kanału, statystyki (widoki, subskrypcje, liczba filmów), ID playlisty uploads, surowy JSON.
- **Tabela `videos`**: ID, ID kanału, tytuł, opis, data publikacji, czas trwania, miniatura, statystyki (widoki, lajki, komentarze), status "Watch Later", surowy JSON.
- **Tabela `metadata`**: Przechowuje datę ostatniej synchronizacji.

## 5. Przepływ Logiczny i Synchronizacja

### 5.1. Synchronizacja Danych
1. Pobierz aktualną listę subskrypcji i zaktualizuj tabelę `channels`.
2. Pobierz datę ostatniej synchronizacji z tabeli `metadata`.
3. Jeśli użytkownik podał `--date-limit`, użyj tej daty jako początku synchronizacji.
4. Pobierz statystyki kanałów z bazy (średnia dzienna liczba filmów z ostatnich 3 miesięcy).
5. Pobierz wszystkie nowe filmy od daty ostatniej synchronizacji do dzisiaj, używając adaptacyjnej wielkości paczek (`maxResults`):
   - Dla każdego kanału: `maxResults = max(średnia_dzienna * dni_od_ostatniego_sync, 2)`.
   - Jeśli kanał jest nowy (brak danych): `maxResults = 10`.
   - Wartość jest ograniczona do maksimum 50 (limit API).
6. Zapisz nowe filmy w bazie danych (używając `ON CONFLICT DO UPDATE`, aby zachować status "Watch Later" dla istniejących filmów).
7. Zaktualizuj datę ostatniej synchronizacji w `metadata`.


### 5.2. Interfejs TUI (Dual-Pane)
1. **Lewy panel:** Lista filmów pogrupowana datami.
   - Nawigacja: `j`/`k` lub strzałki. Możliwość poprzedzenia ruchem liczby (np. `5j` przeskakuje o 5 filmów).
   - Skróty Vim:
     - `gg` - skok na początek listy.
     - `G` - skok na koniec listy (lub `[numer]G` skok do konkretnej linii).
     - `J` / `K` - skok o jeden dzień w dół / w górę (można poprzedzić liczbą, np. `3J`).
     - `zz` - wycentrowanie widoku na aktualnie wybranym filmie.
     - `y` - kopiowanie linku URL wybranego filmu do schowka (wymaga `xclip` lub `wl-copy`).
     - `o` - otwarcie filmu w domyślnej przeglądarce.
     - `l` - dodanie filmu do listy "Watch Later" (Obejrzyj później).
     - `L` - przełączenie widoku na listę "Watch Later".
     - `d` - usunięcie filmu z listy "Watch Later".
     - `/` - wyszukiwanie i filtrowanie filmów po tytule lub nazwie kanału.
   - Inne:
     - `?` - wyświetlenie ekranu pomocy ze skrótami.
     - `ESC` - powrót do głównej listy i wyczyszczenie wszystkich filtrów (wyszukiwania, kanału, listy "Watch Later").
     - `q` - wyjście z aplikacji.
   - Numeracja linii: Względna numeracja linii (jak w Vim), ułatwiająca skoki o określoną liczbę pozycji.
   - Przewijanie o pełne strony: `PageUp`/`PageDown` oraz skróty Vim: `Ctrl+b` (góra) / `Ctrl+f` (dół).
   - Filtrowanie: `s` (przełączanie Shortów), `S` (ustawienie progu czasu dla Shortów), `b` (wyświetlanie tylko filmów aktualnego kanału).
   - Kolorystyka: Konfigurowalne kolory pastelowe dla kropki, czasu, kanału i tytułu (plik `config.json`).
   - Wybór oznaczony kolorową kropką (`•`) i podświetleniem tła.
2. **Prawy panel:** Szczegółowe informacje o wybranym filmie.

## 6. Konfiguracja (`config.json`)
Użytkownik może personalizować wygląd TUI poprzez edycję pliku `config.json`:
- `colors`: Definicje kolorów (kody 256-kolorowe) dla poszczególnych elementów interfejsu.
- `ui`: Ustawienia proporcji paneli i parametrów przewijania.

