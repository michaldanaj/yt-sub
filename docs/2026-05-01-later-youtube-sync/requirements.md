# Requirements — Synchronizacja listy Later z YouTube

## Cel

Lokalny stan `watch_later` w bazie SQLite jest synchronizowany dwukierunkowo
z dedykowaną playlistą na YouTube. Użytkownik może zarządzać listą "Later"
zarówno w aplikacji, jak i bezpośrednio na YouTube — obie strony zbiegają się
przy każdej synchronizacji.

---

## Konfiguracja

Nowe klucze w `config.json` (sekcja `"youtube"`):

```json
"youtube": {
    "later_playlist_name": "Later",
    "later_playlist_id": ""
}
```

- `later_playlist_name` — wyświetlana i szukana nazwa playlisty na YouTube.
  Jeśli playlista o tej nazwie nie istnieje, zostanie utworzona przy pierwszej
  synchronizacji.
- `later_playlist_id` — ID playlisty (np. `PLxxxxx`). Uzupełniane automatycznie
  po odnalezieniu lub utworzeniu playlisty. Jeśli puste, aplikacja szuka po
  nazwie.

---

## Algorytm synchronizacji (full two-way)

### Pojęcia

| Symbol | Opis |
|---|---|
| `S` | Snapshot — zbiór `{video_id: playlistItem_id}` z poprzedniej synchronizacji (przechowywany lokalnie) |
| `Y` | Aktualny zbiór video_id z playlisty na YouTube (filtrowany do filmów obecnych w lokalnej bazie) |
| `L` | Aktualny zbiór video_id z `watch_later=True` w lokalnej bazie |

### Kroki algorytmu

```
1. Załaduj snapshot S z lokalnego storage.
2. Pobierz Y z YouTube API (playlistItems.list); odfiltruj ID nieznane lokalnie.
3. Załaduj L z bazy.

4. Oblicz różnice:
   yt_added    = Y - S.keys()   → dodane na YT od ostatniego sync
   yt_removed  = S.keys() - Y   → usunięte na YT od ostatniego sync
   local_added = L - S.keys()   → dodane lokalnie od ostatniego sync
   local_removed = S.keys() - L → usunięte lokalnie od ostatniego sync

5. Zaaplikuj:
   for id in yt_added:     db.update_watch_later(id, True)
   for id in yt_removed:   db.update_watch_later(id, False)
   for id in local_added:  playlistItem_id = yt.add_to_playlist(playlist_id, id)
   for id in local_removed: yt.remove_from_playlist(S[id])  # używa playlistItem_id

6. Oblicz nowy snapshot:
   new_S = {id: item_id for (id, item_id) in Y_with_ids}
   new_S.update({id: new_item_id for id in local_added})
   # local_removed są już nieobecne w new_S

7. Zapisz new_S jako nowy snapshot.
```

### Pierwsza synchronizacja (S = {})

- `yt_added` = Y → wszystkie filmy z YT są oznaczane lokalnie
- `local_added` = L → wszystkie lokalne Later są pushowane do YT
- Wynik: pełne połączenie obu zbiorów

### Filmy nieznane lokalnie (w Y, ale nie w bazie)

Pomijane — nie są importowane do bazy, nie są usuwane z playlisty YT.
Pozostają na playliście YT bez zmian.

---

## Przechowywanie snapshot

Nowa tabela SQLite `later_sync_snapshot`:

```sql
CREATE TABLE IF NOT EXISTS later_sync_snapshot (
    video_id TEXT PRIMARY KEY,
    playlist_item_id TEXT NOT NULL
);
```

Cała zawartość tabeli = snapshot `S`. Przy zapisie nowego snapshotu:
tabela jest czyszczona i wypełniana od nowa (operacja atomowa w transakcji).

---

## Nowe metody YouTube API (`youtube_client.py`)

| Metoda | Opis |
|---|---|
| `find_or_create_playlist(name: str) -> str` | Szuka playlisty po nazwie (playlists.list, max 50 stron), tworzy jeśli nie istnieje. Zwraca playlist_id. |
| `get_playlist_items(playlist_id: str) -> dict[str, str]` | Zwraca `{video_id: playlistItem_id}` dla całej playlisty (paginacja). |
| `add_to_playlist(playlist_id: str, video_id: str) -> str` | Dodaje film do playlisty. Zwraca playlistItem_id. |
| `remove_from_playlist(playlist_item_id: str) -> None` | Usuwa wpis z playlisty po playlistItem_id. |

---

## Nowy moduł `later_sync.py`

Wyodrębniona logika synchronizacji jako funkcja:

```python
def sync_later(db: Database, yt: YouTubeClient, config: dict) -> SyncResult:
    """Wykonuje pełny two-way sync listy Later."""
```

`SyncResult` — dataclass z polami:
- `added_locally: int`
- `removed_locally: int`
- `added_to_yt: int`
- `removed_from_yt: int`
- `errors: list[str]`

---

## Wyzwalacze synchronizacji

| Wyzwalacz | Opis |
|---|---|
| Start aplikacji | Sync odbywa się w tle (osobny wątek daemon), wynik trafia do TUI przez istniejący `sync_queue`. TUI wyświetla komunikat po zakończeniu. |

Ręczny trigger (`r` / `Ctrl+R`) jest planowany jako część osobnego feature
"Odświeżenie zawartości" (całościowa synchronizacja ręczna), który obejmie
też sync filmów i innych danych.

---

## Zmiany w `tui.py`

- Obsługa nowego typu wiadomości z kolejki `sync_queue`:
  `{"type": "later_sync_done", "result": SyncResult}` — wyświetla podsumowanie
  w pasku statusu (np. `"Later: +2 lokalnie, +1 na YT"`)
- Po `later_sync_done` odświeżenie `display_items` (może zmieniły się flagi
  `watch_later`)

---

## Zmiany w `main.py`

- `sync_later` jest wywoływane w tle przy starcie, po zakończeniu
  podstawowego sync filmów

---

## Obsługa błędów

- Jeśli API zwróci błąd przy konkretnej operacji (np. film usunięty z YT przed
  dodaniem), operacja jest logowana, pozostałe wykonywane
- Jeśli całkowity fetch YT nie powiedzie się, sync jest pomijany (snapshot
  bez zmian)
- Błędy z `errors` w `SyncResult` są wyświetlane w TUI lub logowane do
  `sync_error.log`

---

## Przydziały API (quota)

| Operacja | Koszt |
|---|---|
| `playlists.list` | 1 unit/strona |
| `playlistItems.list` | 1 unit/strona |
| `playlistItems.insert` | 50 units |
| `playlistItems.delete` | 50 units |

Synchronizacja jest kosztowna przy dużej liczbie zmian. W typowym scenariuszu
(kilka zmian od ostatniego sync) koszt jest niski.

---

## Decyzje projektowe

- **Snapshot przechowywany w SQLite** — spójny z resztą danych; transakcyjny
  zapis gwarantuje brak częściowego stanu.
- **Filmy nieznane lokalnie ignorowane** — upraszcza algorytm; użytkownik
  zarządza bazą filmów przez normalny sync kanałów.
- **`later_playlist_id` w config.json** — to konfiguracja (nie zmienia się),
  nie dane runtime; zapis po odnalezieniu/utworzeniu playlisty.
- **Brak ręcznego triggera** — ręczny sync Later będzie częścią osobnego
  feature "Odświeżenie zawartości".
