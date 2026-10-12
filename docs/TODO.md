W aplikacji yt-viewer podoba mi się kolor i ta kropeczka która przechodzi jako
kursor.

## [x] #1 Synchronizacja listy Later z Youtube (duży)

- Lista Later z yt-subs może być synchronizowana z YouTube
- Nazwa listy na YouTube jest konfigurowalna. Jeśli nie istnieje, utworzenie jej
- Po uruchomieniu aplikacji, następuje synchronizacja z listą
- Algorytm synchronizacji musi uwzględniać możliwość dodania lub usuwania filmu
  poza aplikacją i odpowiednio synchronizować zmiany lokalnie

## [x] #2 Natychmiastowy sync Later przy lokalnej zmianie (średni)

Gdy użytkownik dodaje (`l`) lub usuwa (`d` z widoku Later) film z lokalnej listy
Later, zmiana powinna być od razu propagowana do playlisty na YouTube (bez
czekania na pełny sync przy starcie). Wywołanie API w tle, żeby nie blokować
TUI.

Uwaga: wymaga dostępu do `YouTubeClient` i snapshootu z poziomu obsługi klawisza
w TUI — warto ocenić czy nie psuje architektury za bardzo zanim się
implementuje. Chyba najprościej byłoby to zrobić poprzez wywołanie standardowej
synchronizacji listy?

## [x] #3 Przeskakiwanie (mały)

Przeskakiwanie wielu linii, gdy data jest po drodze. Propozycja, że liczba linii
do przeskoczenia mówi o liczbie linii na ekranie, a nie o liczbie pozycji listy.
Jeśli linią do przeskoczenia jest linia z datą, a nie filmem, kursor powinien
ustawić się na pierwszej pozycji po dacie.

## [ ] #4 Informacje o kanale (duży)

Osobny view z informacjami o wybranym kanale i możliwością wykonywania działań
na nim.

Informacje o kanale

- Nazwa
- Data założenia
- Kiedy zasubkrybowałem
- data pierwszego zsynchronizowanego filmu
- Opis
- Id
- Wszystkie inne dostępne
- Ile filmów, ile nie shortów

Statystyki, może w podziale ile w ostatnich 3 miesiącach, ile w dostępnej
historii

- ile filmów, oraz ile średnio miesięcznie
- ile nie shortów, oraz ile średnio miesięcznie
- ile shortów, oraz ile średnio miesięcznie
- średnia długość filmu
- średnia długość filmu po usunięciu shortów

Przejście do listy filmów z tego kanału, w standardowym widoku listy filmów z
filtrem.

Zrobić hierarchię kategorii kanałów.

Może jakieś wykresy z aktywnością po miesiącach? Może już to w trybie graficznym
wyświetlać a nie tekstowym?

## [ ] #5 Ukrywanie kanałów (mały)

Możliwość ukrywania z listy filmów niektórych kanałów, ale pozostawienie ich
jako zasubsrybowane. Dodać taką informację do formatki z info o kanale i
możliwość edycji tego.

## [ ] #6 Ściąganie za wybrany okres z gui dla wszystkich kanałów (średni)

## [ ] #7 Ściąganie za wybrany okres z gui dla wybranego kanału (średni)

## [x] #8 Odświeżenie zawartości — ręczna synchronizacja (mały)

Skrót klawiszowy `r` / `Ctrl+R` uruchamia pełną synchronizację na żądanie, bez
potrzeby restartu aplikacji. Synchronizacja obejmuje:

- Pobranie nowych filmów z kanałów (jak przy starcie)
- Synchronizację listy Later z YouTube (two-way sync)

Sync odbywa się w tle — TUI pozostaje responsywne, pasek statusu pokazuje postęp
i wynik. Jeśli sync już trwa, ponowne wciśnięcie `r`/`Ctrl+R` jest ignorowane.

## [x] #9 Zestawienie kanałów ze statystykami (średni)

Wyświetlenie statystyk kanałów w tabeli i możliwość ich sortowania

## [x] #10 Thumbnail jako opcja (mały)

Skrót do usunięcia thumbnail z widoku i jako opcja w ustawieniach.

## [ ] #11 Zmiana nazwy aplikacji (mały)

Zmiana nazwy na yt-subs. W instalatorze zmienić.

## [ ] #12 Obejrzane (?) (średni)

Dodać tak jak w kliencie pocztowym, że po przejechaniu przez wpis i zatrzymaniu
się na nim na czas przeczytania (np. 1s), zaznaczy się jakoś jako zapoznane.

Zastanowić się czy w ogóle jest sens tej funkcjonalności.

## [ ] #13 Zaznaczenie nowych (średni)

Nowe filmy które pojawiły się od ostatniego przeglądania jakoś powinny być
odznaczone. Żeby nie kolorować ich, może jakąś linią?

## [ ] #14 Wywołanie streszczenia (bardzo duży)

Dla wybranego filmu chciałbym zrobić automatyczną notatkę przez llm-a z
wykorzystaniem aplikacji do transkrypcji. Powinno być wywołane gui z
wypełnieniem pola linku.

Z poziomu aplikacji powinna być możliwość przejrzenia do jakich filmów notatki
zostały zapisane.

## [ ] #15 Konfiguracja (mały)

Jeśli jeszcze nie jest to zrobione, aplikacja powinna instalować się w systemie
zachowując miejsca domyślne konfiguracji i bazy danych. Ścieżki te powinny być
konfigurowalne w konfiguracji.

- Zastanowić się czy nie zmienić formatu pliku z konfiguracją.
- Dać komentarze w pliku z konfiguracją.
- Opisać konfigurację w podręczniku użytkownika

## [ ] #16 Podręcznik użytkownika (średni)

Napisać i utrzymywać.

## [ ] #17 Info o odtwarzaniu (mały)

dodać info, że uruchamia się odtwarzanie, bo teraz nie wiadomo tego. I najlepiej
jeszcze uruchomić je jako nieblokujące.

## [ ] #18 Przechowywanie thumbnails (mały)

Rozważyć przeniesienie ich z cache do katalogu z bazą danych, albo wręcz do bazy
danych.

## [x] #19 Poruszanie się po liście statystyk

Dodać do listy statystyk taką obsługę klawiszy do poruszania się i wyszukiwania
jak na liście filmów.

## [ ] #20 Escape liniowy powrót

Zapamiętuje kolejność działań typu zmiana widoku, filtr, i przy Escape, cofa się
o jeden.

---

# Dekompozycja #4 Informacje o kanale

Rozbicie dużego feature'u #4 na zadania trwające 1-3 godziny. Punkt #4 powyżej
pozostaje jako "parasol" opisujący całość; poniższe pozycje to konkretne kroki
implementacyjne, które można realizować i mergować niezależnie.

## [ ] #4.1 Pobieranie metadanych kanału z YouTube API (1-2h)

- Nowa metoda w `YouTubeClient` wywołująca endpoint `channels.list`
  (parts: `snippet`, `statistics`, `brandingSettings`, `contentDetails`).
- Mapowanie odpowiedzi na dataclass/model `ChannelInfo` (nazwa, data założenia,
  opis, ID, liczba subów, liczba filmów, kraj, custom URL itd.).
- Testy jednostkowe parsowania odpowiedzi (mock HTTP).

## [ ] #4.2 Przechowywanie metadanych kanału w bazie (1-2h)

- Migracja schematu — dodanie kolumn lub osobnej tabeli `channel_info`
  (data założenia, opis, snippet, statistics, timestamp ostatniego pobrania).
- Funkcja zapisująca/aktualizująca rekord po pobraniu z API.
- Cache: nie odświeżać częściej niż raz na X godzin/dni (do ustalenia w spec).

## [ ] #4.3 Widok ChannelInfoView — szkielet i nawigacja (2-3h)

- Nowy widok TUI z layoutem panelów (informacje + statystyki + akcje).
- Skrót klawiszowy otwierający widok z listy filmów (kursor na filmie kanału)
  oraz z widoku zestawienia kanałów (#9).
- Powrót do poprzedniego widoku przez `Escape` (bez zaginania historii widoków).

## [ ] #4.4 Wyświetlenie podstawowych informacji o kanale (1-2h)

- Nazwa, data założenia, data subskrypcji, data pierwszego zsynchronizowanego
  filmu, opis, ID kanału, custom URL, kraj, liczba subskrybentów.
- Render w panelu informacyjnym ChannelInfoView z formatowaniem.

## [ ] #4.5 Liczniki filmów i shortów (1-2h)

- Obliczenie z lokalnej bazy: ile wszystkich filmów, ile shortów, ile nie-shortów.
- Wyświetlenie w panelu informacyjnym.
- Wyznaczenie heurystyki shorta (długość ≤60s) — udokumentować w spec.

## [ ] #4.6 Statystyki częstotliwości publikacji (2-3h)

- Liczba filmów / shortów / nie-shortów w ostatnich 3 miesiącach oraz w pełnej
  zsynchronizowanej historii.
- Średnia miesięczna dla każdej kategorii.
- Tabela porównawcza w panelu statystyk ChannelInfoView.

## [ ] #4.7 Statystyki długości filmów (1-2h)

- Średnia długość filmu (ze shortami i bez) w ostatnich 3 miesiącach i w pełnej
  historii.
- Render w panelu statystyk obok #4.6.

## [ ] #4.8 Przejście do listy filmów z filtrem kanału (1h)

- Akcja w ChannelInfoView (skrót klawiszowy) — otwiera standardową listę filmów
  z aktywnym filtrem `channel_id` wybranego kanału.
- Powrót przez `Escape` zgodnie z #4.3.

## [ ] #4.9 Hierarchia kategorii kanałów — model danych (2h)

- Migracja: tabela `channel_categories` z relacją self-referencing parent
  (drzewo), oraz FK z `channels` do kategorii.
- Funkcje CRUD na poziomie warstwy dostępu do bazy.

## [ ] #4.10 Hierarchia kategorii kanałów — UI edycji (2-3h)

- W ChannelInfoView pole pokazujące przypisaną kategorię + akcja zmiany.
- Mini-widok / popup do nawigacji po drzewie kategorii (dodaj, zmień nazwę,
  usuń, przenieś).

## [ ] #4.11 Wykres aktywności miesięcznej — tryb tekstowy (2h)

- Bar chart ASCII / Unicode pokazujący liczbę filmów na miesiąc w pełnej
  historii kanału.
- Renderowany w ChannelInfoView poniżej statystyk.

## [ ] #4.12 Wykres aktywności — tryb graficzny (opcjonalne, 2-3h)

- Decyzja techniczna: zewnętrzne okno GUI (matplotlib) vs obrazek w terminalu
  (kitty/iTerm protocol) — wymaga ustalenia w spec przed implementacją.
- PoC po akceptacji wybranej drogi.
