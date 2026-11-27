# Patch 00 – Inicializácia backendu (zadanie 1)

Pracovný technický základ pre zadanie 1. Pôvodný README a dokumentácia troch zadaní zostávajú nezmenené. Implementačný stack je návrh tímu, nie predpísaná technológia.

## Čo je zahrnuté

- Sedem samostatne spustiteľných FastAPI procesov: Gateway, Model, File, Training, Provider, Chat a Runtime.
- Jeden lokálny PostgreSQL server so šiestimi oddelenými databázami a nesuperužívateľskými rolami. Každá služba dostáva iba vlastné databázové meno a účet. Heslo je pre lokálny vývoj spoločné; pre reálne nasadenie vyžaduje oddelené tajomstvá. Práva k cudzím DB sú odobraté roli PUBLIC.
- RabbitMQ a sieť Docker Compose; k brokeru sa pripája Model, Training, Provider, Chat a Runtime (nie File).
- Samostatné persistentné volumes pre PostgreSQL, RabbitMQ, súbory a runtime artefakty. Úložiská sú zatiaľ prázdne.
- `/healthz` (živý proces) a `/readyz` (reálne pripojenie na vlastnú DB a podľa služby broker; Gateway kontroluje všetkých šesť služieb). 503 pri nedostupnosti závislosti. Žiadne heslá v odpovedi.
- Základné testy, smoke test a GitHub Actions.

## Lokálne spustenie

Požiadavky: Git, Python 3.12, Docker Desktop/Engine a Compose v2. Príkazy spúšťať z koreňa repozitára:

```bash
cp -n .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 240
docker compose ps
python tests/smoke_compose.py
```

Gateway: http://127.0.0.1:8000/docs (len infra endpointy), http://127.0.0.1:8000/healthz a http://127.0.0.1:8000/readyz. Pri obsadenom porte zmeň `GATEWAY_PORT` v `.env` (napr. 8001) a spusti `python tests/smoke_compose.py http://127.0.0.1:8001`. Databáza, broker a doménové služby nie sú publikované na hostiteľský stroj.

Pri chybe: `docker compose ps -a` a `docker compose logs --tail=80`. Konfiguráciu `.env` necommitovať ani nezdieľať. Prístupové údaje z príkladu sú výlučne lokálne vývojové hodnoty. PostgreSQL init skript sa vykonáva iba pri vytvorení nového DB volume; zmena hesiel v existujúcej inštancii vyžaduje samostatnú správu účtov.

Zastavenie bez odstránenia dát: `docker compose down`. Nepoužívať `down -v`, ak chceš zachovať dáta. CI používa `down -v` iba na vlastnom jednorazovom runneri.

## Git workflow

`main` = spoločný repozitár, `zadanie-1` = integračná vetva tímu, `feat/z1-project-initialization` = pracovná vetva Patch 00. Po lokálnych testoch commit, push, PR s base `zadanie-1`, review kolegom, zelené CI a merge. Do `main` iba podľa dohody s vyučujúcou.

## Hranice Patch 00

Neimplementuje žiadnu z 37 doménových trás, autentifikáciu, smerovanie API, schémy, migrácie, fronty správ, outbox, poskytovateľov, Ollama, tréning ani GPU detekciu. Gateway zatiaľ poskytuje iba infra endpointy, nie proxy. Služby používajú spoločný minimálny Dockerfile a zoznam závislostí, kým nemajú vlastné doménové požiadavky. Readiness je iba infra kontrola, nie dôkaz funkčnej pripravenosti LLM. Knižnice a obrazy nie sú plne transitive/digest locknuté. Patch 01 má pripraviť spoločné kontrakty a bezpečnostnú vrstvu. Runtime pri reálnom využití Apple GPU bude potrebovať natívny hostiteľský režim; Docker runtime je zatiaľ len HTTP kostra. Technický spike inferencie a fine-tuningu zostáva samostatnou otvorenou úlohou. Žiadne skutočné zdravotné údaje ani platené API nie sú potrebné.
