# AtlasRAG — Orquestrador/RAG de Catálogo de Dados e APIs

Monorepo com frontend (React + TS) e backend (FastAPI) para catalogar schemas Postgres, documentar APIs e responder perguntas via RAG com pgvector + OpenAI.

## Por que FastAPI no backend?
FastAPI oferece tipagem moderna em Python, ótima DX com OpenAPI automático, validação sólida (Pydantic) e velocidade para prototipar um MVP com integrações em Postgres e OpenAI, mantendo o código simples e extensível.

## Stack
- **Backend**: FastAPI + SQLAlchemy + Alembic + pgvector
- **Frontend**: React + TypeScript + Vite + MUI + TanStack Query
- **Banco do app**: Postgres + pgvector

## Estrutura do repo
```
backend/        # API FastAPI + migrations
frontend/       # React UI (MVC)
docker-compose.yml
```

## Requisitos
- Docker + Docker Compose
- Node.js 18+
- Python 3.11+

## Variáveis de ambiente
Crie um `.env` (ou exporte no shell) com:
```
OPENAI_API_KEY=...
APP_ENCRYPTION_KEY=<generate_me>
DATABASE_URL=postgresql+psycopg2://atlas:atlas@localhost:5432/atlas
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
CORS_ALLOW_CREDENTIALS=false
```

> **Nota:** `APP_ENCRYPTION_KEY` é obrigatória para criptografar credenciais de conexão. Gere com:
> `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
> Configure `CORS_ORIGINS` com uma lista separada por vírgulas (sem `*` quando `CORS_ALLOW_CREDENTIALS=true`).

## Subir com Docker
```
docker-compose up --build
```

### Migrações
```
cd backend
alembic upgrade head
```

### Seed demo (API route)
```
cd backend
python -m app.seed_demo
```

### Criar schema demo no app-db (para testar scan)
```
psql postgresql://atlas:atlas@localhost:5432/atlas -f backend/demo_schema.sql
```

## Rodar localmente
### Backend
```
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend
```
cd frontend
npm install
npm run dev
```

## Fluxo MVP
1) **Criar conexão Postgres** via UI ou API.
2) **Disparar scan** em `/connections/:id/scan`.
3) **Explorar e etiquetar** tabelas/colunas na UI.
4) **Catalogar API Routes** manualmente.
5) **Reindexar** com `POST /rag/index`.
6) **Perguntar** via `POST /rag/ask`.

### Conexão demo sugerida
- name: Demo App DB
- host: localhost
- port: 5432
- database: atlas
- user: atlas
- password: atlas
- ssl_mode: prefer

## Endpoints principais
- `POST/GET/PUT/DELETE /connections`
- `POST /connections/:id/test`
- `POST /connections/:id/scan`
- `GET /connections/:id/scans`
- `GET /scans/:scanId/schema`
- `GET /tables/:tableId/samples`
- `PUT /tables/:tableId/annotations`
- `PUT /columns/:columnId/annotations`
- `CRUD /api-routes`
- `POST /rag/index`
- `POST /rag/ask`

## Notas de segurança
- Senhas são criptografadas com `APP_ENCRYPTION_KEY`.
- Logs são estruturados e sem segredos.
- `/rag/ask` tem rate limit básico em memória.

## Scripts
### Backend
```
pytest
```

### Frontend
```
npm run lint
npm run test
```
