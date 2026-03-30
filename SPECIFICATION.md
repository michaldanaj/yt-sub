# Specyfikacja Techniczna: YouTube Subscription Monitor

## 1. Cel Aplikacji
Aplikacja służy do pobierania i wyświetlania najnowszych filmów z kanałów subskrybowanych przez użytkownika na platformie YouTube, z możliwością filtrowania po dacie publikacji.

## 2. Architektura i Technologie
- **Język:** Python (lub dowolny z obsługą HTTP/JSON).
- **API:** YouTube Data API v3.
- **Autoryzacja:** OAuth 2.0 (Flow: Installed Application).
- **Zarządzanie sesją:** Serializacja tokenów dostępu do pliku (np. `.pickle` lub `.json`) w celu uniknięcia ponownego logowania.

## 3. Konfiguracja i Zależności
- Wymagane biblioteki do obsługi:
  - Google Auth (OAuthlib, HTTP-client).
  - Google API Client (YouTube discovery service).
- Wymagany plik klienta OAuth (`client_secret_*.json`) pobrany z Google Cloud Console.
- Zakres uprawnień (Scopes): `https://www.googleapis.com/auth/youtube.force-ssl` (lub węższy, np. `readonly`, jeśli nie są wymagane modyfikacje).

## 4. Szczegółowy Przepływ Logicznny

### 4.1. Moduł Autoryzacji
1. Sprawdź, czy istnieje lokalny plik z zapisanymi poświadczeniami (`credentials.pickle`).
2. Jeśli plik istnieje: wczytaj poświadczenia.
3. Jeśli nie:
   - Zainicjuj przepływ OAuth 2.0 (`InstalledAppFlow`) przy użyciu pliku sekretów klienta.
   - Uruchom lokalny serwer w celu przechwycenia kodu autoryzacyjnego.
   - Po uzyskaniu tokena, zapisz go lokalnie do pliku.
4. Zwróć zainicjowany obiekt usługi YouTube API.

### 4.2. Pobieranie Listy Subskrypcji
1. Wywołaj metodę `subscriptions().list`.
2. Parametry: `part="snippet"`, `mine=True`, `maxResults=50`.
3. Obsłuż paginację za pomocą `nextPageToken`, aż pobierzesz wszystkie kanały.
4. Zwróć listę identyfikatorów kanałów (`channelId`).

### 4.3. Pobieranie Filmów z Kanałów
Dla każdego pobranego `channelId`:
1. **Pobranie Playlisty Wgrywania:**
   - Wywołaj `channels().list` z `part="contentDetails"` dla danego `id`.
   - Z odpowiedzi pobierz `contentDetails -> relatedPlaylists -> uploads`. Jest to ID specjalnej playlisty zawierającej wszystkie filmy przesłane na dany kanał.
   - *Optymalizacja:* Można wysyłać zapytania o wiele kanałów naraz (batching), oddzielając ID przecinkami (limit ok. 50 ID na zapytanie).
2. **Pobranie Elementów Playlisty:**
   - Wywołaj `playlistItems().list` dla każdego `uploads` playlist ID.
   - Parametry: `part="snippet,contentDetails"`, `maxResults=10`.
3. **Filtrowanie (opcjonalne):**
   - Jeśli użytkownik podał datę graniczną, odfiltruj filmy, których `snippet.publishedAt` jest wcześniejsze niż podana data (format RFC3339).

### 4.4. Przetwarzanie i Prezentacja Wyników
1. Agreguj wszystkie filmy do jednej listy.
2. Posortuj listę malejąco według daty publikacji (`publishedAt`).
3. Wyświetl sformatowane wyniki (np. `YYYY-MM-DD - Nazwa Kanału - Tytuł Filmu`).

## 5. Obsługa Błędów
- Aplikacja powinna ignorować błędy HTTP przy pobieraniu konkretnych playlist (np. gdy kanał jest usunięty lub prywatny) i kontynuować przetwarzanie pozostałych.
- Należy walidować format daty wprowadzany przez użytkownika (oczekiwany: `YYYY-MM-DD`).

## 6. Możliwe Rozszerzenia (Analiza kodu)
- W kodzie znajduje się nieaktywna funkcja `get_subscriptions`, która analizuje `topicCategories` kanałów. Może ona służyć w przyszłości do grupowania subskrypcji według tematyki (np. Technologia, Rozrywka).
