# Online Exam Question Randomization Tool

Starter implementation using Flask, Flask-SQLAlchemy, Flask-Login, and SQLite for local development.

## Features in this starter
- Teacher login (development seed account)
- Question bank for four-option MCQs
- Exam configuration by subject, question count, duration, and difficulty
- Random question selection without enumerating all combinations
- Randomized option order stored with each generated paper
- Printable generated-paper preview

## 1. Requirements
- Python 3.10 or newer
- VS Code (recommended)

## 2. Create and activate a virtual environment

Windows PowerShell:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows Command Prompt:
```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install packages
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Run
```bash
python run.py
```
Open http://127.0.0.1:5000

Development teacher login:
- Username: `teacher`
- Password: `ChangeMe123!`

This seed account is for local development only. Change the password and remove automatic seeding before deployment. Do not expose the debug server to the public internet.

## 5. First test
1. Sign in.
2. Open Question bank and add at least 3 questions with the same subject, e.g. `DBMS`.
3. Create an exam with that exact subject and a question count no greater than the number of matching questions.
4. Click Generate paper.
5. Refresh or generate again to observe different random selections/order.

## Database
The default local database is created automatically at `instance/exam_randomizer.db`.

To use PostgreSQL later, set `DATABASE_URL` in a `.env` file and install a PostgreSQL driver such as `psycopg[binary]`. The database schema is an initial prototype; use Flask-Migrate/Alembic before making schema changes in a deployed system.

## Important limitations
- This is a learning/MVP scaffold, not production-ready.
- CSRF protection, registration flows, password reset, exam attempts, answer submission, grading, and audit logs are not implemented yet.
- Option shuffling is stored as the original option keys. The displayed option labels are currently numbered in the preview; a later phase should show stable option IDs and implement a separate answer key.
