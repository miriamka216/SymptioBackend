# Patch 01 – Spoločné kontrakty (zadanie 1)

Spoločné stavebné bloky v `shared/` podľa časti „Spoločné konvencie“ a „Spoločný formát chyby“ v `Zadanie 1 - Modely, FineTuning, Používanie/API.md`. Doménové trasy ešte nepribudli; File Service má zatiaľ napojené iba chybové handlery.

## Čo je zahrnuté

| Súbor | Obsah |
|---|---|
| `shared/errors.py` | `ErrorResponse` presne podľa API.md, `ErrorCode` (všetkých 48 kódov z API.md + kódy nižšie, každý s HTTP stavom), výnimka `ApiError`, `install_error_handlers(app)`. Chyba v query → `422 INVALID_QUERY`, v tele → `422 VALIDATION_ERROR` s `details.fields`, neočakávaná → `500 INTERNAL_ERROR` bez interných detailov (traceback iba do logu). |
| `shared/auth.py` | `require_identity` → `Identity(user_id)` z `Authorization: Bearer <token>`. Chýbajúci alebo neznámy token → `401 UNAUTHENTICATED` s `WWW-Authenticate: Bearer`. |
| `shared/idempotency.py` | `require_idempotency_key` (povinný) a `optional_idempotency_key`. Chýba, je prázdny alebo dlhší ako 255 znakov → `422 VALIDATION_ERROR`, `details.fields[].field = "Idempotency-Key"`. |
| `shared/pagination.py` | `pagination_params` (`cursor` nepovinný, `limit` 1–100, predvolene 20) a generický `Page[T]` (`items`, `next_cursor`). |
| `shared/responses.py` | `AcceptedResponse` – základ odpovede 202 (`status`, `status_url`); ID pole pridá služba. |
| `shared/events.py` | `EventEnvelope` – obálka správy pre broker: `message_id` (UUID), `type` (napr. `model.download.requested`), `occurred_at` (vždy UTC), `data`. |
| `shared/health.py` | Bez zmeny (Patch 00). `/readyz` si ponecháva vlastný infra formát. |

## Použitie v službe

```python
from fastapi import Depends

from shared.auth import Identity, require_identity
from shared.errors import ApiError, ErrorCode, install_error_handlers
from shared.health import create_app, postgres_ready
from shared.idempotency import require_idempotency_key
from shared.pagination import Page, PaginationParams, pagination_params
from shared.responses import AcceptedResponse

app = create_app("model-service", {"postgres": postgres_ready})
install_error_handlers(app)


class DownloadAccepted(AcceptedResponse):
    download_id: str


@app.get("/api/v1/models/{model_id}")
def get_model(model_id: str, identity: Identity = Depends(require_identity)):
    raise ApiError(ErrorCode.MODEL_NOT_FOUND, "Model neexistuje.", details={"model_id": model_id})


@app.get("/api/v1/models", response_model=Page[dict])
def list_models(
    page: PaginationParams = Depends(pagination_params),
    identity: Identity = Depends(require_identity),
):
    return Page[dict](items=[], next_cursor=None)


@app.post("/api/v1/model-downloads", status_code=202, response_model=DownloadAccepted)
def start_download(
    identity: Identity = Depends(require_identity),
    idempotency_key: str = Depends(require_idempotency_key),
):
    return DownloadAccepted(download_id="dl_01", status="queued", status_url="/api/v1/model-downloads/dl_01")
```

## Náš návrh mimo API.md

- Kódy `UNAUTHENTICATED` (401), `FORBIDDEN` (403) a `INTERNAL_ERROR` (500). API.md uvádza len stavy 401/403 a pre 500 kód nemá.
- Hlavička `X-Request-ID`: prevezme sa, ak má 1–128 znakov `A–Z a–z 0–9 . _ -`, inak sa vygeneruje `req_<32 hex>`. Vracia sa v tele chyby aj v hlavičke.
- `Idempotency-Key` je na endpointoch spúšťajúcich asynchrónnu prácu povinný, max. 255 znakov, chyba ako `422 VALIDATION_ERROR`. API.md povinnosť, dĺžku ani kód chyby neurčuje.
- **Dočasná autentifikácia:** premenná `EVALVO_DEV_TOKENS="token:user_id,token:user_id"` (príklad v `.env.example`). Celá logika je v jednej funkcii `require_identity`, ktorú neskôr nahradí reálna autentifikácia. Chybná položka v premennej je chyba konfigurácie (500).
- Obálka udalostí `EventEnvelope` a tvar `type` (`domena.udalost.stav`, malé písmená, bodky).

## Vedome odložené

- Ukladanie Idempotency-Key (väzba na identitu a operáciu, 24 h), vrátenie pôvodného ID a `409 IDEMPOTENCY_CONFLICT`.
- Outbox a odosielanie správ do RabbitMQ.
- Reálna autentifikácia, oprávnenia k zdrojom a `403 FORBIDDEN`.
- Spoločný formát pre 404/405 neexistujúcej trasy alebo metódy (teraz FastAPI `{"detail": ...}`).
- Odovzdanie `EVALVO_DEV_TOKENS` do kontajnerov v `docker-compose.yml` – až keď ju prvá služba začne používať.

## Otvorené otázky

- §19 metriky používajú `after_step` a `limit`, ale vracajú `next_cursor` – vzťah k `pagination_params` dorieši Training Service.

## Testy

```bash
source .venv/bin/activate
python -m pytest -q
```

`tests/test_errors.py` overuje formát chyby a všetky kódy priamo proti API.md, `tests/test_contracts.py` auth, idempotenciu, stránkovanie, 202 odpoveď a udalosti. Docker ani databáza nie sú potrebné.
