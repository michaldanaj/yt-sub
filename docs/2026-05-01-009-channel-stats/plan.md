# Plan — #9 Zestawienie kanałów ze statystykami

## Grupa 1: Dane — `database.py`

1. Dodaj dataclass `ChannelStatRow` w `models.py` (lub lokalnie w `database.py`):
   `channel_id`, `channel_title`, `avg_per_month`, `avg_non_short_per_month`,
   `median_duration_seconds`.
2. Zaimplementuj `Database.get_channels_stats_table(months, threshold_seconds)`
   pobierającą filmy z ostatnich `months * 30` dni, grupującą po kanale
   i obliczającą statystyki (`statistics.median` dla mediany).

## Grupa 2: Nowy moduł `channels_stats.py`

3. Utwórz `src/yt_sub/channels_stats.py` z klasą `ChannelsStatsView`:
   - `__init__(db, config)` — ładuje dane przez `db.get_channels_stats_table`,
     ustawia stan sortowania (kolumna 1, rosnąco).
   - `run(stdscr) -> str | None` — własna pętla zdarzeń; zwraca
     `channel_id` po Enter lub `None` po ESC/`a`.
   - `_draw(stdscr)` — rysuje nagłówek, wiersze tabeli i pasek statusu.
   - `_prompt_months(stdscr)` — mini-prompt dla klawisza `m`; zapisuje
     do `config.json` i przeładowuje dane.

## Grupa 3: Integracja z `tui.py`

4. W `YouTubeTUI._handle_key` dodaj obsługę `a`:
   - Zaimportuj i uruchom `ChannelsStatsView(self.db, self.config).run(stdscr)`.
   - Jeśli zwróciło `channel_id`, ustaw `self.filter_channel_id` i odśwież
     `display_items`.

## Grupa 3: Konfiguracja

5. Dodaj `"stats_months": 3` do domyślnego configa w `_load_config`.
6. `ChannelsStatsView._prompt_months` waliduje `1–24` i zapisuje do `config.json`
   (analogicznie do `_set_shorts_threshold`).

## Grupa 4: Dokumentacja

7. Dodaj `a` do tabeli skrótów w `_draw_help_overlay`.
8. Zaktualizuj `SPECIFICATION.md`.
9. Oznacz #9 jako `[x]` w `TODO.md`.
