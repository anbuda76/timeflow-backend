# TimeFlow — Backend API

FastAPI + PostgreSQL + Alembic · Deploy su Render

## Stack
- **FastAPI** 0.115 — framework API
- **SQLAlchemy** 2.0 — ORM con typed mapped columns
- **Alembic** — migrazioni DB
- **PostgreSQL** — database (hosted su Render)
- **JWT** (python-jose) — autenticazione stateless
- **bcrypt** (passlib) — hashing password

---

## Setup locale

```bash
# 1. Clona e installa
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Crea il file .env
cp .env.example .env
# → modifica DATABASE_URL e SECRET_KEY

# 3. Crea il DB PostgreSQL locale
createdb timesheet_db

# 4. Esegui le migrazioni
alembic upgrade head

# 5. Avvia il server
uvicorn app.main:app --reload
```

API disponibile su: http://localhost:8000  
Docs interattive: http://localhost:8000/docs

---

## Struttura progetto

```
app/
├── api/v1/
│   └── endpoints/
│       ├── auth.py          # login, refresh token
│       ├── organizations.py # gestione tenant (super admin)
│       ├── users.py         # CRUD utenti
│       ├── projects.py      # CRUD progetti + assegnazioni
│       ├── timesheets.py    # timesheet + entries + workflow
│       ├── reports.py       # costo risorse mensile
│       └── holidays.py      # festività e chiusure
├── core/
│   ├── config.py            # settings da .env
│   ├── security.py          # JWT + bcrypt
│   └── deps.py              # dipendenze FastAPI (auth, ruoli)
├── db/
│   └── session.py           # engine SQLAlchemy + get_db
├── models/
│   └── models.py            # tutti i modelli ORM
├── schemas/
│   └── schemas.py           # tutti gli schemi Pydantic
└── main.py                  # app FastAPI + CORS + router
```

---

## Ruoli utente

| Ruolo | Può fare |
|-------|----------|
| `super_admin` | Gestisce tutte le organizzazioni |
| `admin` | Gestisce utenti, progetti, report della propria org |
| `manager` | Approva/rifiuta timesheet del team |
| `employee` | Inserisce ore, invia timesheet |

---

## API principali

```
POST   /api/v1/auth/login              Login → JWT
POST   /api/v1/auth/refresh            Refresh token

GET    /api/v1/organizations           Lista org (super admin)
POST   /api/v1/organizations           Crea org + admin

GET    /api/v1/users                   Lista utenti
POST   /api/v1/users                   Crea utente
PATCH  /api/v1/users/{id}              Modifica utente

GET    /api/v1/projects                Lista progetti
POST   /api/v1/projects                Crea progetto
POST   /api/v1/projects/{id}/assign/{user_id}  Assegna utente

GET    /api/v1/timesheets              Lista timesheet
POST   /api/v1/timesheets              Crea timesheet (mese)
PUT    /api/v1/timesheets/{id}/entries Salva griglia ore
POST   /api/v1/timesheets/{id}/submit  Invia per approvazione
POST   /api/v1/timesheets/{id}/review  Approva/Rifiuta (manager)

GET    /api/v1/reports/costs?year=&month=  Costo risorse mensile

GET    /api/v1/holidays                Festività organizzazione
POST   /api/v1/holidays                Aggiungi festività
DELETE /api/v1/holidays/{id}           Rimuovi festività
```

---

## Deploy su Render

Il file `render.yaml` configura automaticamente:
- Web Service (FastAPI) su piano Starter
- PostgreSQL Basic-256mb
- Auto-migrate al deploy (`alembic upgrade head`)
- SECRET_KEY generata automaticamente da Render

```bash
# Prima push
git init && git add . && git commit -m "initial"
# Collega repo su dashboard.render.com → New Blueprint
```

---

## Prossimi step
- [ ] Frontend React (repo separato)
- [ ] Modulo BCT (registrazione passeggeri barche)
- [ ] Export Excel/PDF dei report
- [ ] Email notifiche (approvazioni)
