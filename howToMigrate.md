# Database Migrations Guide

## How it works

Every time a DB column or table is added, a migration file is created in `backend/db/migrations/versions/`. These files are committed to git. When you pull changes that include a new migration file, you apply it once and your DB is up to date.

---

## Docker (automatic)

Nothing to do. Migrations run automatically every time the backend container starts.

```bash
docker compose up --build -d
```

---

## Local environment (manual)

### First-time setup on a new machine

1. Start PostgreSQL:

   ```bash
   docker compose up postgres -d
   ```

2. Apply all migrations:

   ```bash
   PYTHONPATH=. alembic upgrade head
   ```

   `if - command not found: alembic`

   ```bash
   source .venv/bin/activate
   pip install -e .
   PYTHONPATH=. alembic upgrade head
   ```

   `if the tables already exist in the DB and getting errors try running:`

   ```bash
   source .venv/bin/activate
   PYTHONPATH=. alembic stamp head
   ```

3. Start each service in its own terminal:

   ```bash
   # Terminal 1
   uvicorn backend.main:app --host 0.0.0.0 --port 4101 OR
   PYTHONPATH=. .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 4101

   # Terminal 2
   uvicorn ai_service.main:app --host 0.0.0.0 --port 4102 OR
   PYTHONPATH=. .venv/bin/uvicorn ai_service.main:app --host 0.0.0.0 --port 4102
   ```

---

### After pulling changes from git

Check if there are new migration files:

```bash
git pull
ls backend/db/migrations/versions/
```

If you see a new file that wasn't there before, run:

```bash
PYTHONPATH=. alembic upgrade head
```

Then start your services as normal. If no new migration files appeared, skip the migration step entirely.

---

## Adding a new migration (when you change a model)

1. Edit the model in `backend/db/models.py`

2. Generate the migration file:

   ```bash
   PYTHONPATH=. alembic revision --autogenerate -m "short description of the change"
   ```

3. Open the generated file in `backend/db/migrations/versions/` and verify it looks correct

4. Apply it locally:

   ```bash
   PYTHONPATH=. alembic upgrade head
   ```

5. Commit both files — the model change and the migration file:
   ```bash
   git add backend/db/models.py backend/db/migrations/versions/
   git commit -m "add output_dir column to runs"
   ```

When your teammates pull this commit, they just run `alembic upgrade head` and they're in sync.

---

## Useful commands

| Command                | What it does                              |
| ---------------------- | ----------------------------------------- |
| `alembic upgrade head` | Apply all pending migrations              |
| `alembic downgrade -1` | Roll back the last migration              |
| `alembic current`      | Show which migration is currently applied |
| `alembic history`      | List all migrations in order              |

---

## One-time setup on a machine that already has data (no Alembic yet)

If your DB was created before Alembic was introduced (tables exist but Alembic has never run), do this once:

```bash
# Add any columns that exist in the models but not yet in the DB
docker exec -it stocks-agents-postgres-1 psql -U sa_user -d stock_agents -c \
  "ALTER TABLE runs ADD COLUMN IF NOT EXISTS output_dir TEXT;"

# Tell Alembic the initial migration is already applied
PYTHONPATH=. alembic stamp head
```

After that, follow the normal workflow above.
