# Walidacja — Feature #10

## Kryteria akceptacji

### Klawisz `t`

- [x] `t` ukrywa thumbnail (prawy panel wypełnia całą wysokość).
- [x] `t` ponownie — thumbnail wraca.
- [x] Stan persystuje po restarcie aplikacji (zapisany w `config.json`).

### Konfiguracja

- [x] `config.json` zawiera `"show_thumbnails": true/false` po toggle.
- [x] Uruchomienie z `"show_thumbnails": false` — thumbnaily domyślnie ukryte.

### Brak regresji

- [x] Przy włączonych thumbnailach zachowanie identyczne z poprzednim.
- [x] `thumbnails.clear_kitty()` wywoływane przy wyłączaniu (brak artefaktów).
- [x] Inne skróty (`s`, `b`, `/` itd.) działają bez zmian.
