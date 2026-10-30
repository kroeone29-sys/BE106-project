# BE106 Backend Project

A Flask-based backend API project for BE106, structured for production-style development and deployment readiness.

## Setup

1. Clone the repository:
    ```bash
    git clone https://github.com/kroeone29-sys/BE106-project
    cd BE106-project
    ```

2. Create and activate a virtual environment (Python 3.11+ recommended):
    ```bash
    python -m venv .venv
    source .venv/bin/activate # macOS/Linux 
    # On Windows: .venv\Scripts\activate
    ```

3. Upgrade `pip` (recommended):
    ```bash
    pip install --upgrade pip
    ```

4. Install dependencies:
    ```bash
    pip install -r requirements.txt

## Environment Variables

This project uses a `.env` file for local configuration. An example template is provided in `.env.example`.

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set values appropriate for your environment:

   - `JWT_SECRET` – secret string used for signing JWTs and other security-related features.
   - `DATABASE_URL` – (optional in development) database connection string. If not set, development will default to `sqlite:///dev.db`.

> Note: Never commit your real `.env` file. It is listed in `.gitignore` and should remain local only.


## Database Migrations

This project does not yet use an automated migration tool (such as Flask-Migrate or Alembic).

For now:

- Development uses a local SQLite database by default (`sqlite:///dev.db`) when `DATABASE_URL` is not set.
- If you change models or schema, you may need to recreate your local database manually during development.