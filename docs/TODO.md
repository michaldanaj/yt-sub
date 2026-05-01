W aplikacji yt-viewer podoba mi się kolor i ta kropeczka która przechodzi jako
kursor.

## [x] #1 Synchronizacja listy Later z Youtube (duży)

- Lista Later z yt-subs może być synchronizowana z YouTube
- Nazwa listy na YouTube jest konfigurowalna. Jeśli nie istnieje, utworzenie jej
- Po uruchomieniu aplikacji, następuje synchronizacja z listą
- Algorytm synchronizacji musi uwzględniać możliwość dodania lub usuwania filmu
  poza aplikacją i odpowiednio synchronizować zmiany lokalnie

## [ ] #2 Natychmiastowy sync Later przy lokalnej zmianie (średni)

Gdy użytkownik dodaje (`l`) lub usuwa (`d` z widoku Later) film z lokalnej listy
Later, zmiana powinna być od razu propagowana do playlisty na YouTube (bez
czekania na pełny sync przy starcie). Wywołanie API w tle, żeby nie blokować TUI.

Uwaga: wymaga dostępu do `YouTubeClient` i snapshootu z poziomu obsługi klawisza
w TUI — warto ocenić czy nie psuje architektury za bardzo zanim się implementuje.

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

Statystyki, może w podziale ile w ostatnich 3 miesiącach, ile w dostępnej
historii

- ile filmów, oraz ile średnio miesięcznie
- ile nie shortów, oraz ile średnio miesięcznie
- ile shortów, oraz ile średnio miesięcznie
- średnia długość filmu
- średnia długość filmu po usunięciu shortów

Przejście do listy filmów z tego kanału, w standardowym widoku listy filmów z
filtrem.

## [ ] #5 Ukrywanie kanałów (mały)

Możliwość ukrywania z listy filmów niektórych kanałów, ale pozostawienie ich
jako zasubsrybowane. Dodać taką informację do formatki z info o kanale i
możliwość edycji tego.

## [ ] #6 Ściąganie za wybrany okres z gui dla wszystkich kanałów (średni)

## [ ] #7 Ściąganie za wybrany okres z gui dla wybranego kanału (średni)

## [x] #8 Odświeżenie zawartości — ręczna synchronizacja (mały)

Skrót klawiszowy `r` / `Ctrl+R` uruchamia pełną synchronizację na żądanie,
bez potrzeby restartu aplikacji. Synchronizacja obejmuje:

- Pobranie nowych filmów z kanałów (jak przy starcie)
- Synchronizację listy Later z YouTube (two-way sync)

Sync odbywa się w tle — TUI pozostaje responsywne, pasek statusu pokazuje
postęp i wynik. Jeśli sync już trwa, ponowne wciśnięcie `r`/`Ctrl+R` jest
ignorowane.

## [ ] #9 Zestawienie kanałów ze statystykami (średni)

Wyświetlenie statystyk kanałów w tabeli i możliwość ich sortowania

## [ ] #10 Thumbnail jako opcja (mały)

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

## [ ] #18 Gdzie thumbnails (mały)

Rozważyć przeniesienie ich z cache do katalogu z bazą danych, albo wręcz do bazy
danych.

## [x] #19 Poruszanie się po liście statystyk

Dodać do listy statystyk taką obsługę klawiszy do poruszania się i wyszukiwania jak na liście filmów.

