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


## Running with Docker Compose (Flask + PostgreSQL)

This project supports running the Flask application and PostgreSQL database together using Docker Compose.

### Prerequisites

- Docker installed and running
- Docker Compose available through the Docker CLI

### 1. Build the Web Image

From the project root directory (where the `Dockerfile` is located):

```bash
docker build -t enginelog-app:local .
```

### 2. Start the Application Stack

Start both the Flask application and PostgreSQL database:

```bash
docker compose up
```

Docker Compose starts two services:

- **db:** PostgreSQL 16 database with persistent storage through a named Docker volume.
- **web:** Flask application served by Gunicorn, using the same `create_app()` application factory as local development.

The application is exposed on port `8000`.

Leave this terminal running to monitor application and database logs.

### 3. Apply Database Migrations

Open a separate terminal from the project root and execute:

```bash
docker exec -it be106-project-web-1 flask db upgrade
```

This applies all pending Flask-Migrate migrations to the PostgreSQL database.

### 4. Verify Application Health

From the host machine, send a request to the health endpoint:

```bash
curl -i http://localhost:8000/health
```

Expected response:

**HTTP Status:**

```http
HTTP/1.1 200 OK
```

**Response Body:**

```json
{
  "status": "ok"
}
```

A successful response confirms that the application is responding to health checks.

### 5. Stop the Application Stack

Stop the running services using `Ctrl+C` in the terminal running Docker Compose.

Then execute:

```bash
docker compose down
```

This stops and removes the application and database containers while preserving the PostgreSQL data stored in the named Docker volume.

To remove the database volume and its persistent data as well:

```bash
docker compose down -v
```

**Warning:** Removing the volume permanently deletes the PostgreSQL data stored in it.

### Architecture Overview

```text
Host Machine
    |
    | localhost:8000
    |
Docker Compose
    |
    +-- web
    |     |
    |     +-- Gunicorn
    |     +-- Flask Application
    |     +-- create_app()
    |     +-- Flask-Migrate
    |
    +-- db
          |
          +-- PostgreSQL 16
          +-- Persistent Named Volume
```

The application and database run as separate services within the same Docker Compose network. The Flask application communicates with PostgreSQL through the configured database connection.

The Docker deployment uses the existing Flask application factory, keeping application initialization consistent between local development and containerized execution.
