# webhook-receiver

A prototype webhook receiver service built with FastAPI, asyncio, and SQLite.
Prototyp webhook-receiver w FastAPI, asynctio i SQLite

## Metodologia pracy

Na początek metodologia jaką przyjąłem, bo ona wiele wyjaśnia.

- postanowiłem użyć Claude Code jako partnera w projektowaniu, oraz generatora kodu
- po przyjrzeniu się zadaniu, stworzyłem sobie [listę pytań i decyzji do podjęcia](docs/todos.md)
- skopiowałem template ADR chcąc tworzyć ADRy, by z nich w całości wygenerować kod
- zagadnienia w wybranej przez siebie kolejności omawiałem z Claude Code, a podjęte decyzje dokumentowałem w ADRach (generowane, dlatego takie długie, ale dość trafnie oddają wnioski)
- po zakończeniu omawiania najważniejszych zagadnień, pozostałe rozbiłem na [pojedyncze proste pytania](docs/adr/other_details_and_decisions.md) na które odpowiedziałem
- następnie Claude [skompilował decyzje do jednego pliku](docs/decisions.md)
- na podstawie pliku z decyzjami, iteracyjnie generowałem kod
- następnie wygenerowałem load testy, które wykazały potrzebę tuningu (ilość workerów) oraz nieścisłości w implementacji vs decyzje (twarde limitowanie queue)
- wprowadziłem poprawki
- opisałem projekt w tym README.md

## Architektura

Webhooki są persystowane w SQLite przed przetwarzaniem, gwarantując **at-least-once** przetworzenie nawet w przypadku awarii.

```
POST /webhooks
      │
      ▼
SQLiteIdempotencyStore ──► tabela events
      │
      ▼ (if new)
AsyncioEventQueue
      │
      ▼
N asynchronicznych workerów ──► oznacz event jako processing ──► [sleep 2-5s] ──► oznacz completed/failed
```

**Kluczowe komponenty**

| Moduł              | Odpowiedzialność                                                                   |
| ------------------ | ---------------------------------------------------------------------------------- |
| `router.py`        | HTTP, idempotency check, backpressure (429)                                        |
| `store.py`         | `SQLiteIdempotencyStore` — query do bazy, retry                                    |
| `workers.py`       | workery, przetwarzanie eventów w `process_event`, logika startupu w `load_pending` |
| `cleanup.py`       | Cyklicznie usuwa przedawnione eventy                                               |
| `metrics.py`       | Metryki do prometeusza                                                             |
| `config.py`        | `Settings` via `pydantic-settings` / konfifurowalne przez envy                     |
| `logging_setup.py` | Konfiguracja logowania                                                             |

## Konfiguracja

Zmienne środowiskowe, nadpisywać w `mise.toml`

| Variable                 | Default           | Description                                                                  |
| ------------------------ | ----------------- | ---------------------------------------------------------------------------- |
| `DB_PATH`                | `/data/events.db` | SQLite file path                                                             |
| `WORKER_COUNT`           | `85`              | Liczba workerów ~(1000 (requestów) / 60 (sekund) \* 5 (max processing time)) |
| `QUEUE_MAXSIZE`          | `1000`            | Pojemność kolejki                                                            |
| `MAX_ATTEMPTS`           | `5`               | Max liczba prób przetworzenia eventu                                         |
| `RETRY_BASE_DELAY`       | `5.0`             | Exponential backoff base (seconds)                                           |
| `RETRY_MAX_DELAY`        | `300.0`           | Backoff cap (seconds)                                                        |
| `RETENTION_DAYS`         | `30`              | Ile dni trzymamy eventy                                                      |
| `CLEANUP_INTERVAL_HOURS` | `1`               | Jak często uruchamiamy cleanup                                               |
| `LOG_LEVEL`              | `INFO`            | Domyślny log level                                                           |

## Schemat bazy ##

Schemat bazy jest [dostępny tutaj](src/webhook_receiver/schema.sql)

* jedna tabelka, bo bardziej jest to inbox pattern, niż np. event sourcing.
* 4 statusy: pending, processing, completed, failed
  - pending - oczekuje na przetworzenie
  - processing - jest przetwarzane, na wypadek awarii/restartu
  - completed - przetworzony
  - failed - przetwarzanie nie powiodło się
* jeden indeks, bo ogarnia najcięższe wymienione w wymaganiach zapytania.

## Jak uruchomić

Trzeba mieć zainstalowane [mise](https://mise.jdx.dev/installing-mise.html)

```bash
mise install
start
```

Albo z Dockerem

```bash
build_docker
start_docker
```

[Interaktywne API](`http://localhost:8000/docs`)

## Jak testować

### Jednostkowo

```bash
test
```

### Obciążeniowo

```bash
locust_1000_headless # testuje tylko POST /webhooks
locust_final_headless # testuje POST /webhooks i GET /webhooks/{id}
```

Komendy bez `_headless` uruchamiają interaktywne UI Locusta.

## Kluczowe decyzje i trade-offy

- **In-process asyncio queue** — czyli `asyncio.Queue` i mnogo workerów zapewniających rozdzielenie przyjmownia eventów od ich przetwarzania. Prosto bo prototyp, ale łatwo zastąpić na Redis Streams/RabbitMQ
- **SQLiteIdempotencyStore** - pilnuje unikalności `idempotency_key`, zawsze pyta się bazy, bo trzeba zwracać aktualny status. Wydajność zapewnia `UNIQUE` na `idempotency_key`.
- **At-least-once processing** — eventy mogą być przetworzone wiele razy w przypadku awarii/restartu, ale prościej jest
- **Bounded queue + 429** — backpressure, kolejka nie powinna rosnąć w nieskończoność. Jednocześnie kolejka nie jest sama w sobie ograniczona, żeby nie powodować błędu przy starcie w sytuacji, gdy liczba nieprzetworzonych eventów w bazie przekracza wielkość kolejki
- **Single SQLite connection + WAL mode** — szybszy przy współbieżnym dostępie (85 workerów + API)
- **Composite index `(status, created_at)`** — pokrywa query na startupie, cleanup i zapytania dla monitoringu. Gdyby chcieć listować eventy, można jeszcze dodać index na samo `created_at` i/lub `updated_at`
- **Hard delete** — usunięcie przeterminowanych eventów, nie ma soft delete. Jeśli chodzi o audytowalność, to można dodać append-only event log
- **Rate limiting** - nie ma, bo moim zdaniem powinien być w reverse proxy (12-factor), reverse proxy nie chciałem robić w prototypie

## Obserwowalność

Metryki Prometheus pod `/metrics`:

- `webhook_events_total{result}` — licznik eventów (`accepted` / `duplicate` / `rejected`)
- `webhook_queue_depth` — długość kolejki
- `webhook_processing_duration_seconds` — histogram czasu przetwarzania eventu
- `webhook_processing_errors_total` — licznik błędów

## Wnioski na przyszłość i TODOsy

- (meta) nie jestem pewien, czy dobrze zinterpretowałem słowo "prototyp", i czy założenie minimalizacji infrastruktury było trafne, czy chodziło raczej o to, żeby zaprząc do pracy Redisa/RabbitMQ/RevProxy i tylko kodu nie dopieszczać
- ten kod jest brzydki, ale działa, i jest szybki. Ale wymaga gruntownej restrukturyzacji (bo teraz płaska struktura) i refactoru.
- logi są plain text, ale na prod bym użył OpenTelemetry i trace'ingu w logach 
- żeby system był rozproszony i skalowalny, EventQueue oparłbym na Redis Streams i grupach konkurujących konsumentów dla at-least-once processing
- możnaby też oprzeć IdempotencyStore o Redisa `idempotency_key:status`, pilnując, by workery aktualizowały status w Redisie, ale to z kolei wprowadza brak pojedynczego źródła prawdy i ryzyko inconsistency
- możnaby dodać oddzielny append-only event log na wszystkie zdarzenia dt. przetwarzania eventów i usuwania starych
- exactly-once processing gdyby użyć distributed locking
