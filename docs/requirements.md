# Webhook Receiver Service - Zadanie rekrutacyjne

[Oryginał Łukasza Kałużnego](https://gist.github.com/kaluzaaa/fcd035829013d9952f71a9a6a59a4d2f#file-gist_webhook_receiver-md)

## Czas i zakres

- Działający prototyp, nie system produkcyjny.
- Python, FastAPI
- Skup się na architekturze i decyzjach projektowych, nie na dopieszczaniu kodu.
- Kod zgodny z PEP 8.

## Cel

Stwórz **HTTP API**, które przyjmuje webhooki (zdarzenia w formacie JSON), gwarantuje ich przetworzenie i udostępnia status każdego zdarzenia.

## Przykład użycia

System zewnętrzny wysyła powiadomienia (webhooki) do Twojego serwisu. Każde zdarzenie ma unikalny klucz (`idempotency_key`). Serwis musi zagwarantować, że każde zdarzenie zostanie przetworzone **dokładnie raz**, nawet jeśli zostanie wysłane wielokrotnie.

**Przykładowe webhooki:**

```json
{
  "idempotency_key": "evt-001",
  "event_type": "order.created",
  "payload": {
    "order_id": "ORD-2024-1234",
    "customer": "Jan Kowalski",
    "amount": 299.99,
    "currency": "PLN"
  }
}
```

```json
{
  "idempotency_key": "evt-002",
  "event_type": "order.paid",
  "payload": {
    "order_id": "ORD-2024-1234",
    "payment_method": "card",
    "paid_at": "2024-12-01T14:30:00Z"
  }
}
```

```json
{
  "idempotency_key": "evt-003",
  "event_type": "order.shipped",
  "payload": {
    "order_id": "ORD-2024-1234",
    "tracking_number": "PL1234567890",
    "carrier": "DPD"
  }
}
```

```json
{
  "idempotency_key": "evt-004",
  "event_type": "user.registered",
  "payload": {
    "user_id": "USR-9876",
    "email": "jan@example.com"
  }
}
```

```json
{
  "idempotency_key": "evt-005",
  "event_type": "payment.failed",
  "payload": {
    "order_id": "ORD-2024-5678",
    "reason": "insufficient_funds"
  }
}
```

**Oczekiwany flow:**

```
System zewnętrzny                         Twój serwis
  │                                          │
  │  1. POST webhook (JSON + idempotency_key)│
  │ ───────────────────────────────────────► │
  │                                          │  zapisuje do SQLite
  │  2. Potwierdza przyjęcie                 │  kolejkuje do przetworzenia
  │ ◄─────────────────────────────────────── │
  │                                          │
  │         ... przetwarzanie ...             │  worker przetwarza async
  │                                          │
  │  3. Sprawdza status                      │
  │ ───────────────────────────────────────► │
  │  np. {"status": "completed"}             │
  │ ◄─────────────────────────────────────── │
  │                                          │
  │  4. Wysyła ten sam webhook ponownie      │
  │     (retry / duplikat)                   │
  │ ───────────────────────────────────────► │
  │                                          │  rozpoznaje duplikat
  │  Zwraca istniejący status (nie przetwarza│  po idempotency_key
  │  ponownie)                               │
  │ ◄─────────────────────────────────────── │
```

**Przetwarzanie** webhooków to symulacja — w prototypie wystarczy `sleep(2-5s)` i zapis wyniku. Focus jest na wzorcach, nie na logice biznesowej.

> Jak dokładnie wygląda API (endpointy, format odpowiedzi, sposób przetwarzania) - to Twoja decyzja projektowa.

## Wymagania biznesowe

1. Każdy przyjęty webhook musi zostać przetworzony — nawet jeśli serwis zostanie zrestartowany.
2. Ten sam webhook wysłany wielokrotnie nie może być przetworzony więcej niż raz.
3. Klient musi mieć możliwość sprawdzenia statusu przetwarzania.
4. Serwis musi działać poprawnie przy wielu równoczesnych webhookach.
5. Dane muszą mieć zdefiniowany czas życia (retencja).

## Kontekst techniczny

### Persystencja

Użyj **SQLite** jako bazy danych. Schemat tabel jest Twoją decyzją projektową.

### Przetwarzanie

Symulacja — przetwarzanie webhooków to `sleep(2-5s)` + zapis wyniku. Nie musisz implementować prawdziwej logiki biznesowej.

### Skala

Wyobraź sobie serwis obsługujący **~1000 webhooków/minutę** z kilku systemów zewnętrznych. Nie musisz tego osiągnąć w prototypie, ale Twoje decyzje architektoniczne powinny to uwzględniać.

## Co oceniamy

Nie szukamy konkretnej architektury - chcemy zobaczyć **jak myślisz o problemach**. W szczególności:

- **Niezawodność** - Jak gwarantujesz, że żaden webhook nie zginie? Co się dzieje przy restarcie serwisu?
- **Idempotency** - Jak rozpoznajesz i obsługujesz duplikaty?
- **Przetwarzanie async** - Jak oddzielasz przyjęcie webhooka od jego przetworzenia?
- **Model danych** - Jak projektujesz schemat SQLite? Jakie indeksy, jakie statusy?
- **Obserwowalność** - Jak zespół operacyjny zrozumie, co robi serwis i zdiagnozuje problemy?
- **Tradeoffs** - Co wybrałeś, z czego zrezygnowałeś i dlaczego?

## Deliverables

- **Działający kod** w Pythonie, który można uruchomić i przetestować.
- **README** zawierające: opis architektury, kluczowe tradeoffs, instrukcje uruchomienia.
- **Dockerfile** do konteneryzacji.
- **Sekcja `# TODO`** (w README lub kodzie) z pomysłami, które zrealizowałbyś mając więcej czasu.

## Punkty bonusowe

- Testy jednostkowe kluczowych komponentów.
- Rate limiting.
- Metryki, endpoint health/readiness.
- Retry logic dla failed webhooków.
- Testy obciążeniowe lub benchmarki.
