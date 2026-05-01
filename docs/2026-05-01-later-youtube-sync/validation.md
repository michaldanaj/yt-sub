# Validation — Synchronizacja listy Later z YouTube

## Warunki wstępne

- Konto Google z dostępem do YouTube API (token OAuth)
- Playlista "Later" może istnieć lub nie na YouTube
- Baza zawiera kilka filmów

---

## SC-1: Pierwsza synchronizacja — playlista nie istnieje

1. Wyczyść `later_playlist_id` w config.json.
2. Usuń playlistę "Later" z YouTube (jeśli istnieje).
3. Oznacz 2 filmy lokalnie jako Watch Later (`l`).
4. Uruchom aplikację.
- **Oczekiwane:** Playlista "Later" została utworzona na YouTube z 2 filmami.
  `later_playlist_id` jest zapisane w config.json.

## SC-2: Pierwsza synchronizacja — playlista istnieje z filmami

1. Wyczyść snapshot (tabela `later_sync_snapshot` pusta).
2. Na YouTube dodaj ręcznie 2 filmy do playlisty "Later" (filmy znane w bazie).
3. Lokalnie oznacz 1 inny film jako Watch Later.
4. Uruchom aplikację.
- **Oczekiwane:** Lokalnie: wszystkie 3 filmy mają `watch_later=True`.
  Na YouTube: playlista zawiera 3 filmy.

## SC-3: Sync dwukierunkowy — zmiany po obu stronach

1. Stan po poprzednim sync: playlista YT = {A, B}, lokalnie = {A, B}.
2. Lokalnie dodaj C, usuń B (przez `d`).
3. Na YouTube ręcznie dodaj D, usuń A.
4. Uruchom aplikację.
- **Oczekiwane:**
  - Lokalnie: `watch_later=True` dla {C, D}, `watch_later=False` dla {A, B}.
  - Na YouTube: playlista = {C, D}.
  - Snapshot = {C: item_id_C, D: item_id_D}.

## SC-4: Film nieznany lokalnie na playliście YT

1. Na YouTube dodaj ręcznie film spoza lokalnej bazy.
2. Uruchom aplikację.
- **Oczekiwane:** Film nieznany pozostaje na playliście YT, nie jest dodawany
  do bazy. Reszta sync działa normalnie.

## SC-5: Automatyczny sync przy starcie

1. Zmodyfikuj stan (lokalnie lub na YT) przed uruchomieniem.
2. Uruchom aplikację.
- **Oczekiwane:** Sync Later wykonuje się w tle po starcie. Pasek statusu
  wyświetla podsumowanie, np. `"Later: +1 lokalnie"`.

## SC-6: Błąd API

1. Odwołaj dostęp OAuth lub użyj nieważnego tokenu.
2. Uruchom aplikację.
- **Oczekiwane:** Błąd jest wyświetlony w pasku statusu lub zalogowany do
  `sync_error.log`. Snapshot pozostaje bez zmian. Aplikacja nie crashuje.
