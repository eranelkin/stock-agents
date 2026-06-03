# Database Migrations Guide

## The one command you need

```bash
python scripts/migrate.py
```

Run this any time you:
- Set up the project on a new machine
- Pull code that contains new migration files
- Are unsure whether your DB schema is up to date

The script auto-detects the state of your database and does the right thing:

| DB state | What it does |
|---|---|
| Fresh (no tables) | Runs all migrations from scratch |
| Legacy (tables exist, Alembic never ran) | Stamps the DB at the right revision, then applies missing changes |
| Already tracked by Alembic | Applies only the pending migrations (no-op if already at head) |

---

## Docker (automatic)

Nothing to do. Migrations run automatically every time the backend container starts.

```bash
docker compose up --build -d
```

---

## Local environment

### First-time setup on a new machine

```bash
# 1. Start PostgreSQL
docker compose up postgres -d

# 2. Activate the virtual environment and install dependencies
source .venv/bin/activate
pip install -e .

# 3. Run migrations (handles everything automatically)
python scripts/migrate.py

# 4. Start the services (each in its own terminal)
PYTHONPATH=. .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 4101
PYTHONPATH=. .venv/bin/uvicorn ai_service.main:app --host 0.0.0.0 --port 4102
```

### After pulling changes from git

```bash
git pull
python scripts/migrate.py   # safe to run even if no new migrations
```

---

## Adding a new migration (when you change a model)

1. Edit the model in `backend/db/models.py`

2. Generate the migration file:
   ```bash
   PYTHONPATH=. alembic revision --autogenerate -m "short description"
   ```

3. Open the generated file in `backend/db/migrations/versions/` and verify it looks correct.
   For `add_column` migrations, make them idempotent:
   ```python
   # Instead of:
   op.add_column("table", sa.Column("col", sa.Text(), nullable=True))

   # Use:
   op.execute("ALTER TABLE table ADD COLUMN IF NOT EXISTS col TEXT")
   ```

4. Update `HEAD` in `scripts/migrate.py` to the new revision ID.

5. Apply locally:
   ```bash
   python scripts/migrate.py
   ```

6. Commit the model change and migration file together:
   ```bash
   git add backend/db/models.py backend/db/migrations/versions/ scripts/migrate.py
   git commit -m "add <column> to <table>"
   ```

When pulling this on another machine, just run `python scripts/migrate.py`.

---

## Useful Alembic commands

| Command | What it does |
|---|---|
| `PYTHONPATH=. alembic current` | Show which revision is currently applied |
| `PYTHONPATH=. alembic history` | List all migrations in order |
| `PYTHONPATH=. alembic upgrade head` | Apply all pending migrations |
| `PYTHONPATH=. alembic downgrade -1` | Roll back the last migration |
