# EngineLog API

A Flask REST API for recording and retrieving user-owned, engine-to-engine handoff receipts. The application uses JWT-based authentication, user-scoped resource access, and a shared Neon PostgreSQL database across local development, local Docker, and Render production.

> **Documentation status:** This README is a review draft assembled from the supplied BE106 application-context artifacts. Confirm the repository-specific details called out in **Items to Verify Before Merging** against the current source code and Render configuration.

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Data Model](#data-model)
- [Authentication and Authorization](#authentication-and-authorization)
- [API Reference](#api-reference)
- [Prerequisites](#prerequisites)
- [1. Clone and Configure the Repository](#1-clone-and-configure-the-repository)
- [2. Run the Flask Development Server](#2-run-the-flask-development-server)
- [3. Build and Run the Docker Container](#3-build-and-run-the-docker-container)
- [4. Verify the Render Production Deployment](#4-verify-the-render-production-deployment)
- [5. Compare All Three Environments](#5-compare-all-three-environments)
- [Environment Variables and Secrets](#environment-variables-and-secrets)
- [Docker Configuration](#docker-configuration)
- [Error Handling and Validation](#error-handling-and-validation)
- [Operational and Security Notes](#operational-and-security-notes)
- [Items to Verify Before Merging](#items-to-verify-before-merging)

## Project Overview

EngineLog records an auditable receipt for a handoff between two engines. Each record identifies:

- The engine that initiated the handoff (`from_engine`).
- The engine that received the handoff (`to_engine`).
- The associated payload identifier (`payload_id`).
- The user who owns the record (`user_id`).
- The record creation timestamp (`created_at`).

The API enforces ownership at the server boundary. A client cannot assign a record to another user by submitting a `user_id` in its request body.

## Architecture

The application is created through a single Flask application factory:

- `create_app()` in `app/__init__.py` is the application entry point.
- `wsgi.py` exposes the application as `wsgi:app` for the WSGI server.
- Feature-specific blueprints organize the routes.

The supplied application context identifies these blueprints:

| Blueprint | URL prefix / responsibility |
|---|---|
| `main_bp` | Core routes, including `/ping` and `/health`, plus any remaining main routes |
| `auth_bp` | Authentication feature, mounted at `/auth` |
| `admin_bp` | Administrative endpoints, mounted at `/admin` |
| `engine_logs_bp` | EngineLog endpoints, mounted at `/engine-logs` |

EngineLog route ownership is isolated in `app/engine_logs/routes.py`. The EngineLog blueprint is defined with the `engine_logs` name and `/engine-logs` URL prefix. EngineLog route logic and helpers belong in this feature module rather than `main.py`.

### Application Request Flow

1. A request reaches the Flask application created by `create_app()`.
2. Flask dispatches the request to the matching blueprint and route.
3. Protected routes validate the bearer token with `@jwt_required`.
4. The decorator places the authenticated user ID in `g.user_id`.
5. EngineLog queries and mutations are scoped to that authenticated user.
6. The route returns the documented JSON response or an appropriate HTTP error.

## Data Model

### User

The User resource represents an account. The supplied context identifies email, a hashed password, an optional display name, and a role.

Passwords must be stored as password hashes, never as plaintext.

### EngineLog

| Field | Purpose |
|---|---|
| `id` | Record identifier |
| `from_engine` | Source engine |
| `to_engine` | Destination engine |
| `payload_id` | Identifier for the handed-off payload |
| `user_id` | Owning user; non-null foreign key to `user.id` |
| `created_at` | Record creation timestamp |

Every EngineLog belongs to exactly one user. The database relationship is enforced by `EngineLog.user_id`, which is `NOT NULL` and references `user.id`.

## Authentication and Authorization

### JWT Authentication

Protected endpoints use the custom `@jwt_required` decorator.

The decorator:

1. Reads the `Authorization` request header.
2. Expects the `Bearer <token>` format.
3. Verifies and decodes the JWT using `JWT_SECRET`.
4. Reads the user identifier from the token's `sub` claim.
5. Sets `g.user_id` to the authenticated user's integer ID.

The supplied context identifies `sub`, `role`, and `exp` as token claims, with an approximately 2,400-second token lifetime.

Example request header:

```http
Authorization: Bearer <JWT_TOKEN>