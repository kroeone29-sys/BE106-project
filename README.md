
# EngineLog API

A Flask REST API for user authentication, profile management, role-based administrative access, and user-owned engine-to-engine traffic logs.

The application uses JWT authentication, SQLAlchemy for database persistence, and a Docker-based production deployment with Gunicorn.

## Features

- User registration with hashed password storage.
- User login with signed JSON Web Tokens (JWT).
- JWT-protected profile endpoints.
- Database-backed role authorization for administrative access.
- EngineLog creation, retrieval, updating, and deletion.
- User-scoped EngineLog resource ownership.
- Paginated EngineLog listing.
- Structured JSON validation and error responses.
- Environment-based configuration for development, testing, and production.
- PostgreSQL support and SQLite development fallback.
- Docker deployment using Gunicorn.

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| Web framework | Flask 3.1.3 |
| ORM | Flask-SQLAlchemy 3.1.1 |
| Database toolkit | SQLAlchemy 2.1.6 |
| Database migrations | Flask-Migrate 4.1.0 / Alembic 1.20.1 |
| Authentication | PyJWT 2.15.1 |
| Password hashing | Werkzeug |
| PostgreSQL driver | psycopg 3.2.13 |
| Environment configuration | python-dotenv 1.2.4 |
| Production server | Gunicorn 27.0.1 |
| Containerization | Docker |

## Project Structure

```text
BE106-project/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   ├── models.py
│   ├── main.py
│   ├── auth/
│   │   └── __init__.py
│   └── engine_logs/
│       └── routes.py
├── wsgi.py
├── requirements.txt
├── Dockerfile
└── .dockerignore
```

## Application Architecture

### Application Factory

The Flask application is created through `create_app()` in `app/__init__.py`.

The factory:

1. Selects the application configuration using `APP_ENV`.
2. Initializes SQLAlchemy and Flask-Migrate.
3. Imports the application models.
4. Registers the application blueprints.
5. Installs application-wide HTTP error handlers.

The application uses separate blueprints for the main API, authentication, administration, and EngineLog resources.

### Authentication

Authentication is implemented through the `jwt_required` decorator in `app/auth/__init__.py`.

The decorator:

1. Reads the `Authorization` request header.
2. Requires the `Bearer` authentication scheme.
3. Extracts and decodes the JWT.
4. Validates the signature using the configured `JWT_SECRET`.
5. Rejects expired or invalid tokens.
6. Establishes the authenticated user's identity through `g.user_id`.

JWTs use the HS256 signing algorithm.

The login endpoint issues tokens containing:
- `sub`: The authenticated user's ID.
- `role`: The literal value `"user"`.
- `exp`: The token expiration timestamp.

The token lifetime is controlled by `JWT_LIFETIME_SECONDS`.

### Authorization

Authentication and authorization are handled as separate concerns.

- **Authentication:** A valid JWT establishes the identity of the requester.
- **Resource authorization:** EngineLog endpoints compare the authenticated user ID against the resource's `user_id`.
- **Role authorization:** The administrative endpoint retrieves the User record and checks its database-backed `role` value.

The administrative check does not rely on the role claim in the JWT.

EngineLog endpoints enforce ownership rather than requiring an administrator role.

## Database Models

The application defines two SQLAlchemy models: `User` and `EngineLog`.

### User

Table: `user`

| Field | Type | Constraints / Default |
|---|---|---|
| `id` | Integer | Primary key |
| `email` | String(255) | Required, unique |
| `password_hash` | String(255) | Required |
| `created_at` | DateTime | Required, database function default |
| `display_name` | String(255) | Nullable |
| `role` | String(20) | Required, defaults to `user` |

Passwords are hashed before persistence. Plaintext passwords are not stored.

The `role` field supports database-backed authorization. The model defaults new accounts to the `user` role.

### EngineLog

Table: `engine_log`

| Field | Type | Constraints / Default |
|---|---|---|
| `id` | Integer | Primary key |
| `user_id` | Integer | Required foreign key to `user.id` |
| `from_engine` | String(255) | Required |
| `to_engine` | String(255) | Required |
| `payload_id` | String(255) | Required |
| `created_at` | DateTime | Required, database function default |

Each EngineLog record belongs to a User through the `user_id` foreign key.

The models define a bidirectional SQLAlchemy relationship using `back_populates`. The User relationship also configures `cascade="all, delete-orphan"` for associated EngineLog records.

## API Reference

The API exposes public endpoints, authenticated user endpoints, administrative endpoints, and EngineLog resource endpoints.

### Health and Availability

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| GET | `/ping` | Public | Basic main-blueprint availability check |
| GET | `/health` | Public | JSON health check |

`GET /health` returns:

```json
{
  "status": "ok"
}
```

### Authentication

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| POST | `/register` | Public | Register a new account |
| POST | `/login` | Public | Authenticate and receive a JWT |
| GET | `/auth/verify` | JWT | Verify the supplied JWT |

#### POST `/register`

Request:

```json
{
  "email": "user@example.com",
  "password": "your-password"
}
```

Successful response: `201 Created`

```json
{
  "id": 1,
  "email": "user@example.com",
  "created_at": "2026-01-01T12:00:00"
}
```

The password is hashed before the User record is persisted.

Possible responses:

- `201`: Account created.
- `400`: Invalid JSON structure or missing password.
- `409`: Email already registered.

#### POST `/login`

Request:

```json
{
  "email": "user@example.com",
  "password": "your-password"
}
```

Successful response: `200 OK`

```json
{
  "token": "<jwt>"
}
```

Possible responses:

- `200`: Authentication successful.
- `400`: Invalid JSON structure or missing password.
- `401`: Invalid email or password.

Unknown email addresses and incorrect passwords return the same `INVALID_CREDENTIALS` response.

#### GET `/auth/verify`

Requires:

```http
Authorization: Bearer <jwt>
```

Successful response: `200 OK`

```json
{
  "ok": true
}
```

### User Profile

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| GET | `/users/me` | JWT | Retrieve the authenticated user's profile |
| PATCH | `/users/me` | JWT | Update the authenticated user's display name |

#### GET `/users/me`

Successful response: `200 OK`

```json
{
  "id": 1,
  "email": "user@example.com",
  "display_name": null
}
```

#### PATCH `/users/me`

Request:

```json
{
  "display_name": "Example User"
}
```

The request must include the `display_name` field.

Successful response: `200 OK`

```json
{
  "id": 1,
  "email": "user@example.com",
  "display_name": "Example User"
}
```

Possible responses:

- `200`: Profile updated.
- `400`: Missing required `display_name` field.
- `401`: Missing, expired, or invalid JWT.
- `404`: Authenticated user's database record not found.

### Administration

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| GET | `/admin/ping` | JWT + admin role | Administrative availability check |

The endpoint retrieves the authenticated user's database record and checks whether `role == "admin"`.

Successful response: `200 OK`

```json
{
  "status": "admin-ok"
}
```

A missing User record or insufficient role returns:

```json
{
  "error": "forbidden"
}
```

HTTP status: `403 Forbidden`

### EngineLog Resources

All EngineLog endpoints require a valid JWT.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/engine-logs` | Create an EngineLog record |
| GET | `/engine-logs` | Retrieve the authenticated user's logs |
| GET | `/engine-logs/<log_id>` | Retrieve one owned log |
| PATCH | `/engine-logs/<log_id>` | Update one owned log |
| DELETE | `/engine-logs/<log_id>` | Delete one owned log |

#### POST `/engine-logs`

Request:

```json
{
  "from_engine": "engine-a",
  "to_engine": "engine-b",
  "payload_id": "payload-123"
}
```

The authenticated user's ID is assigned to `user_id` by the server. The client does not supply the record owner.

The creation timestamp is generated by the application.

Successful response: `201 Created`

```json
{
  "id": 1,
  "user_id": 1,
  "from_engine": "engine-a",
  "to_engine": "engine-b",
  "payload_id": "payload-123",
  "created_at": "2026-01-01T12:00:00+00:00"
}
```

#### GET `/engine-logs`

Supports pagination through query parameters.

| Parameter | Default | Validation |
|---|---|---|
| `page` | 1 | Must be at least 1 |
| `per_page` | 20 | Must be between 1 and 50 |

Example:

```http
GET /engine-logs?page=1&per_page=20
```

The endpoint returns only records belonging to the authenticated user.

Response structure:

```json
{
  "items": [],
  "page": 1,
  "per_page": 20,
  "total": 0,
  "pages": 0
}
```

Records are ordered by their database ID.

An out-of-range page returns an empty `items` array while retaining the pagination metadata.

#### GET `/engine-logs/<log_id>`

Retrieves an individual EngineLog record if it exists and belongs to the authenticated user.

#### PATCH `/engine-logs/<log_id>`

Request:

```json
{
  "from_engine": "engine-a",
  "to_engine": "engine-c",
  "payload_id": "payload-123"
}
```

All three fields are required. Although the HTTP method is PATCH, the current implementation requires the complete set of EngineLog fields rather than supporting individual-field updates.

#### DELETE `/engine-logs/<log_id>`

Deletes an owned EngineLog record.

Successful response: `204 No Content`

#### EngineLog Ownership Behavior

For individual GET, PATCH, and DELETE operations, a record that does not exist and a record owned by another user produce the same `404 NOT_FOUND` response.

This prevents the endpoint from revealing whether another user's record exists.

## Error Handling

The application uses structured JSON responses for validation and resource errors.

### Authentication Errors

The JWT decorator returns these responses:

| Condition | HTTP Status | Error |
|---|---:|---|
| Missing or malformed Bearer header | 401 | `missing_or_malformed_token` |
| Expired JWT | 401 | `token_expired` |
| Invalid JWT | 401 | `invalid_token` |

### Validation Errors

A request body that is not a JSON object returns:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "details": {
      "body": [
        "A JSON object is required."
      ]
    }
  }
}
```

EngineLog validation errors use the same general envelope with an EngineLog-specific message and details.

### Application-Wide Request Errors

The application factory defines global handlers for:

- `400 Bad Request`: Invalid request JSON.
- `415 Unsupported Media Type`: Unsupported request media type.

These handlers return structured JSON error responses.

### Resource Errors

EngineLog resources use a consistent `NOT_FOUND` response for missing or unowned records.

User profile endpoints use `USER_NOT_FOUND` when the authenticated user's database record cannot be found.

## Configuration

Configuration is managed in `app/config.py`.

The application selects its configuration using the `APP_ENV` environment variable.

| Environment Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | Selects application configuration | `development` |
| `DATABASE_URL` | SQLAlchemy database connection URI | None |
| `JWT_SECRET` | JWT signing secret | Development fallback |
| `JWT_LIFETIME_SECONDS` | JWT lifetime in seconds | `2400` |

### Configuration Classes

| Class | Behavior |
|---|---|
| `DevelopmentConfig` | Enables debug mode and falls back to local SQLite |
| `TestingConfig` | Enables testing mode and disables debug mode |
| `ProductionConfig` | Disables debug and testing modes |

Development uses `DATABASE_URL` when supplied. Otherwise, it falls back to an absolute-path SQLite database named `dev.db`.

Testing and production inherit the base database URI configuration. Neither defines a separate database fallback in the current implementation.

### Environment File

The WSGI entrypoint loads environment variables through `python-dotenv` before creating the application.

Create a local `.env` file:

```dotenv
APP_ENV=development
JWT_SECRET=replace-with-a-secure-secret
JWT_LIFETIME_SECONDS=2400
```

For a PostgreSQL deployment, provide the appropriate `DATABASE_URL`:

```dotenv
DATABASE_URL=postgresql+psycopg://username:password@host:5432/database
```

Use the connection URI supplied by your database provider, with credentials and connection parameters appropriate to that environment.

The `.env` file is excluded from the Docker build context.

**Security:** Replace the fallback JWT secret with a strong, unique secret in production. Do not commit `.env` files or production credentials to source control.

## Local Development

### Requirements

- Python 3.11
- pip
- Git
- SQLite for local development, or a supported external database

### 1. Clone the Repository

```bash
git clone <repository-url>
cd BE106-project
```

### 2. Create and Activate a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
APP_ENV=development
JWT_SECRET=replace-with-a-secure-development-secret
```

A local SQLite database is used when `DATABASE_URL` is not supplied.

### 5. Initialize the Database

Apply the database migrations before starting the application:

```bash
python -m flask --app wsgi db upgrade
```

### 6. Start the Development Server

```bash
python -m flask --app wsgi run --debug --port 5011
```

The API will be available at:

```text
http://127.0.0.1:5011
```

---

## Docker Deployment

The Dockerfile builds a Python 3.11-based production image and starts the application with Gunicorn.

### 1. Build the Image

From the project root:

```bash
docker build -t enginelog-api .
```

### 2. Prepare the Production Database

The production database must already have the application's migration schema applied before the container starts.

**Important:** The current Dockerfile does not copy the `migrations/` directory into the image. Database migrations therefore cannot be run from the built container as currently configured.

### 3. Run the Container

Supply the production environment variables at runtime:

```bash
docker run -d \
  --name enginelog-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -e APP_ENV=production \
  -e DATABASE_URL="your-database-connection-string" \
  -e JWT_SECRET="your-secure-production-secret" \
  enginelog-api
```

The application listens on port `8000` inside the container and is exposed on port `8000` of the host.

### Production Server

The Docker image starts Gunicorn using:

```bash
gunicorn --bind 0.0.0.0:8000 wsgi:app
```

The Dockerfile does not copy `.env` files into the image. Production configuration must be supplied through runtime environment variables.

The `.dockerignore` file excludes local virtual environments, Git metadata, Python cache files, environment files, local SQLite database files, instance data, and macOS metadata from the Docker build context.

---

## Dependencies

All Python dependencies are pinned in `requirements.txt`.

Install the listed package versions with:

```bash
python -m pip install -r requirements.txt
```

---

## Current Implementation Notes

The following distinctions describe the current implementation:

- User registration hashes passwords before storing them.
- JWT authentication establishes user identity through `g.user_id`.
- Admin authorization checks the database-backed User role.
- EngineLog resource access is scoped to the authenticated user.
- EngineLog PATCH requires all three resource fields.
- Registration explicitly requires a password but does not implement email-format validation.
- Profile updates require the `display_name` key but do not enforce a non-empty string.
- The Dockerfile copies the application package and WSGI entrypoint, but does not copy migration files or a `.env` file.
- Production database and JWT configuration must be supplied externally.
- The production database schema must be migrated before the application is started.

---

**EngineLog API**  
Flask REST API | JWT Authentication | SQLAlchemy | PostgreSQL | Docker