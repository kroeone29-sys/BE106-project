
"""
Application entrypoint and Flask app factory.

This module defines the application's primary API blueprints and their
request handlers. It provides user registration and authentication,
authenticated profile management, administrative access checks, and
EngineLog resource operations.

Authentication is handled with JWTs. The authenticated user's identity
is supplied by the jwt_required decorator through g.user_id. Resource
ownership is enforced by comparing that identity with the corresponding
database record.
"""

from flask import Blueprint, jsonify, request, g

from app.models import User, EngineLog
from app.extensions import db
from app.auth import jwt_required

from werkzeug.security import generate_password_hash

from datetime import datetime, timedelta, timezone
import jwt
import math

from flask import current_app


main_bp = Blueprint("main", __name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@main_bp.route("/ping")
def ping():
    """
    Provide a basic blueprint availability check.

    Returns:
        A plain-text response confirming that the main blueprint is reachable.
    """
    return "OK from blueprint"


@main_bp.route("/health")
def health():
    """
    Provide a JSON health-check response.

    Returns:
        A 200 response containing the application's basic health status.
    """
    return jsonify({"status": "ok"}), 200


def request_object_validation_error():
    """
    Build a standard VALIDATION_ERROR response when a request body is not
    a JSON object.

    Endpoints that require named fields must receive a JSON object.
    Arrays, strings, numbers, booleans, and null values do not satisfy
    that request structure.

    Returns:
        A 400 response using the standard validation error envelope.
    """
    return jsonify({
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "details": {
                "body": ["A JSON object is required."]
            }
        }
    }), 400


@main_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user account.

    Request Body:
        A JSON object containing:
            - email: The email address for the new account.
            - password: The password for the new account.

    Processing:
        1. Read and validate the JSON request body.
        2. Extract the submitted email and password.
        3. Require a password.
        4. Check whether the email is already registered.
        5. Hash the password before storing it.
        6. Create and persist the new User record.

    Returns:
        - 201 when the account is successfully created.
        - 400 when the JSON structure is invalid or the password is missing.
        - 409 when the submitted email is already registered.

    Security:
        Passwords are hashed before persistence and are never stored
        in plaintext.
    """

    # 1. Read the JSON request body.
    data = request.get_json()

    # 2. Require an object before accessing named fields.
    if not isinstance(data, dict):
        return request_object_validation_error()

    # 3. Extract the submitted registration fields.
    password = data.get("password")
    email = data.get("email")

    # 4. Require a password before creating the account.
    if not password:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid registration data",
                "details": {
                    "password": ["Password is required"]
                }
            }
        }), 400

    # 5. Prevent registration with an email already in use.
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({
            "error": {
                "code": "EMAIL_TAKEN",
                "message": "Email is already taken",
                "details": {
                    "email": ["This email is already in use"]
                }
            }
        }), 409

    # 6. Hash the password before it is persisted.
    hashed = generate_password_hash(password)

    # 7. Create the user record and commit it to the database.
    user = User(email=email, password_hash=hashed)
    db.session.add(user)
    db.session.commit()

    # 8. Return the newly created account details.
    return jsonify({
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at.isoformat()
    }), 201


@main_bp.route("/login", methods=["POST"])
def login():
    """
    Authenticate an existing user and issue a signed JWT.

    Request Body:
        A JSON object containing:
            - email: The account email address.
            - password: The account password.

    Processing:
        1. Read and validate the JSON request body.
        2. Extract the submitted credentials.
        3. Require a password.
        4. Look up the account by email.
        5. Verify the submitted password against its stored hash.
        6. Build and sign a JWT using the configured secret and lifetime.

    Returns:
        - 200 when authentication succeeds, with the signed JWT.
        - 400 when the JSON structure is invalid or the password is missing.
        - 401 when the email or password is incorrect.

    Security:
        - Passwords are verified against their stored hashes.
        - Unknown email addresses and incorrect passwords return the same
          INVALID_CREDENTIALS response to prevent account enumeration.
        - JWTs are signed with the configured JWT secret and expire according
          to JWT_LIFETIME_SECONDS.
    """

    # 1. Read the JSON request body.
    data = request.get_json()

    # 2. Require an object before accessing named fields.
    if not isinstance(data, dict):
        return request_object_validation_error()

    # 3. Extract the submitted login credentials.
    password = data.get("password")
    email = data.get("email")

    # 4. Require a password before attempting authentication.
    if not password:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid login data",
                "details": {
                    "password": ["Password is required"]
                }
            }
        }), 400

    # 5. Look up the account using the submitted email address.
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid email or password",
                "details": {}
            }
        }), 401

    # 6. Verify the submitted password against the stored password hash.
    from werkzeug.security import check_password_hash
    if not check_password_hash(user.password_hash, password):
        return jsonify({
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid email or password",
                "details": {}
            }
        }), 401

    # 7. Build the JWT payload with the configured expiration.
    now = datetime.now(timezone.utc)
    lifetime_seconds = current_app.config.get("JWT_LIFETIME_SECONDS")

    payload = {
        "sub": str(user.id),
        "role": "user",
        "exp": now + timedelta(seconds=lifetime_seconds)
    }

    # 8. Sign the JWT using the configured application secret.
    token = jwt.encode(
        payload,
        current_app.config.get("JWT_SECRET"),
        algorithm="HS256"
    )

    # 9. Return the signed token to the authenticated client.
    return jsonify({"token": token}), 200


@main_bp.route("/users/me", methods=["GET"])
@jwt_required
def get_my_profile():
    """
    Retrieve the authenticated user's profile.

    Authentication:
        Requires a valid JWT. The jwt_required decorator supplies the
        authenticated user's ID through g.user_id.

    Processing:
        1. Read the authenticated user's ID.
        2. Retrieve the corresponding User record.
        3. Return the user's safe profile fields.

    Returns:
        - 200 with the user's profile when the record exists.
        - 404 when no matching User record is found.
    """

    # 1. Read the identity established by the authentication decorator.
    user_id = g.user_id

    # 2. Retrieve the corresponding user record.
    user = User.query.get(user_id)
    if user is None:
        return jsonify({
            "error": {
                "code": "USER_NOT_FOUND",
                "message": "User not found",
                "details": {}
            }
        }), 404

    # 3. Return profile fields that are safe to expose to the user.
    return jsonify({
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
    }), 200


@main_bp.route("/users/me", methods=["PATCH"])
@jwt_required
def update_my_profile():
    """
    Update the authenticated user's profile.

    Request Body:
        A JSON object containing:
            - display_name: The display name to assign to the user.

    Authentication:
        Requires a valid JWT. The jwt_required decorator supplies the
        authenticated user's ID through g.user_id.

    Processing:
        1. Retrieve the authenticated user's database record.
        2. Read the submitted JSON body.
        3. Require the display_name field.
        4. Apply the permitted profile update and commit the change.

    Returns:
        - 200 with the updated profile when the update succeeds.
        - 400 when the required display_name field is missing.
        - 404 when no matching User record is found.
    """

    # 1. Read the authenticated user's ID.
    user_id = g.user_id

    # 2. Retrieve the corresponding user record.
    user = User.query.get(user_id)
    if user is None:
        return jsonify({
            "error": {
                "code": "USER_NOT_FOUND",
                "message": "User not found",
                "details": {}
            }
        }), 404

    # 3. Read the submitted JSON body.
    data = request.get_json() or {}

    # 4. Require the profile field this endpoint permits the user to update.
    if "display_name" not in data:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid update data",
                "details": {
                    "display_name": ["Display name is required"]
                }
            }
        }), 400

    # 5. Apply the permitted update and persist the change.
    user.display_name = data["display_name"]
    db.session.commit()

    # 6. Return the updated profile.
    return jsonify({
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
    }), 200


@admin_bp.route("/ping", methods=["GET"])
@jwt_required
def admin_ping():
    """
    Provide an administrative health check for authenticated administrators.

    Authentication:
        The jwt_required decorator verifies the JWT and supplies the
        authenticated user's ID through g.user_id. Requests without a valid
        token receive a 401 response before this function is called.

    Authorization:
        The user's role is read from the trusted User database record.
        Only users whose database role is "admin" are permitted.

    Returns:
        - 200 when the authenticated user has the admin role.
        - 403 when the user record is missing or the user is not an admin.

    Security:
        Authorization relies on the database role rather than a role value
        supplied in the request body.
    """

    # 1. Read the authenticated identity established by jwt_required.
    user_id = getattr(g, "user_id", None)
    user = User.query.get(user_id)

    # 2. Enforce the admin role using the database record.
    if user is None or user.role != "admin":
        return jsonify({"error": "forbidden"}), 403

    # 3. Return success for an authenticated administrator.
    return jsonify({"status": "admin-ok"}), 200


def engine_log_not_found(log_id: int):
    """
    Build the standard NOT_FOUND JSON response for an EngineLog resource.

    Centralizing this response ensures that GET, PATCH, and DELETE
    operations return the same error envelope when a resource is missing
    or is not owned by the authenticated user.

    Args:
        log_id: The primary key of the requested EngineLog.

    Returns:
        A 404 response with the standard NOT_FOUND error envelope.
    """
    return jsonify({
        "error": {
            "code": "NOT_FOUND",
            "message": "EngineLog not found",
            "details": {
                "log_id": log_id
            }
        }
    }), 404


def engine_log_validation_error(details: dict):
    """
    Build the standard VALIDATION_ERROR JSON response for EngineLog payloads.

    This helper keeps request validation responses consistent across
    EngineLog creation and update operations.

    Args:
        details: Field-level or request-level validation errors.

    Returns:
        A 400 response with the standard VALIDATION_ERROR envelope.
    """
    return jsonify({
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid engine log data",
            "details": details,
        }
    }), 400


@main_bp.route("/engine-logs", methods=["GET"])
@jwt_required
def list_engine_logs():
    """
    List paginated EngineLog records belonging to the authenticated user.

    Authentication:
        Requires a valid JWT. The jwt_required decorator supplies the
        authenticated user's ID through g.user_id.

    Processing:
        1. Read the authenticated user's ID.
        2. Read optional page and per_page query parameters, applying
           default values and validation rules.
        3. Build a query for EngineLog records belonging to that user.
        4. Apply a deterministic ordering to the query.
        5. Apply pagination to return only the requested page of results.
        6. Serialize the current page of records and attach pagination
           metadata describing the full result set.

    Returns:
        A 200 response containing a JSON object with:
            - items: the current page of EngineLog records owned by the
              authenticated user.
            - page: the current page number.
            - per_page: the maximum number of items per page.
            - total: the total number of matching EngineLog records for
              the authenticated user.
            - pages: the total number of available pages at the current
              per_page value.

        If the caller supplies invalid pagination parameters, returns a
        400 response using the standard EngineLog validation error
        envelope.
    """

    # 1. Read the authenticated user's ID.
    user_id = g.user_id

    # 2. Read pagination parameters with defaults.
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # 3. Validate pagination parameters.
    if page is None or page < 1:
        return engine_log_validation_error({
            "page": ["page must be a positive integer (>= 1)."]
        })

    if per_page is None or per_page < 1 or per_page > 50:
        return engine_log_validation_error({
            "per_page": ["per_page must be a positive integer between 1 and 50."]
        })

    # 4. Build the base query for this user's EngineLog records.
    base_query = EngineLog.query.filter_by(user_id=user_id)

    # 5. Compute pagination metadata from the base query.
    total = base_query.count()

    if total == 0:
        pages = 0
    else:
        # you'll need `import math` at the top of app/main.py
        pages = math.ceil(total / per_page)

    # 6. Select the current page of logs from the ordered query.
    offset = (page - 1) * per_page

    logs = (
        base_query
        .order_by(EngineLog.id)
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # 7. Serialize each record into the API response shape.
    log_data = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "from_engine": log.from_engine,
            "to_engine": log.to_engine,
            "payload_id": log.payload_id,
            "created_at": log.created_at.isoformat()
        }
        for log in logs
    ]

    # 8. Return the paginated collection with metadata.
    return jsonify({
        "items": log_data,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }), 200


@main_bp.route("/engine-logs", methods=["POST"])
@jwt_required
def create_engine_log():
    """
    Create a new EngineLog owned by the authenticated user.

    Request Body:
        A JSON object containing all required fields:
            - from_engine
            - to_engine
            - payload_id

    Authentication and ownership:
        Requires a valid JWT. The authenticated user's ID is supplied
        through g.user_id and is used as the new record's owner.
        The client cannot assign ownership through request data.

    Processing:
        1. Read the JSON request body.
        2. Reject a missing body.
        3. Require the top-level JSON value to be an object.
        4. Extract the required EngineLog fields.
        5. Validate that all required fields are present and non-empty.
        6. Create the record using g.user_id as its owner.
        7. Persist the record.
        8. Return the created record.

    Returns:
        - 201 with the created EngineLog when validation succeeds.
        - 400 with a VALIDATION_ERROR envelope when the body is missing,
          is not a JSON object, or fails field-level validation.
    """

    # 1. Read the JSON request body.
    data = request.get_json()

    # 2. Reject a missing JSON body.
    if data is None:
        return engine_log_validation_error({
            "body": ["JSON body is required"]
        })

    # 3. Require an object before accessing named fields.
    if not isinstance(data, dict):
        return request_object_validation_error()

    # 4. Extract the required EngineLog fields.
    from_engine = data.get("from_engine")
    to_engine = data.get("to_engine")
    payload_id = data.get("payload_id")

    # 5. Collect field-level errors for missing or empty values.
    field_errors = {}
    if not from_engine:
        field_errors["from_engine"] = ["from_engine is required"]
    if not to_engine:
        field_errors["to_engine"] = ["to_engine is required"]
    if not payload_id:
        field_errors["payload_id"] = ["payload_id is required"]

    # 6. Return the validation response if any required fields are invalid.
    if field_errors:
        return engine_log_validation_error(field_errors)

    # 7. Create the record using the authenticated user as its owner.
    user_id = g.user_id
    log = EngineLog(
        from_engine=from_engine,
        to_engine=to_engine,
        payload_id=payload_id,
        user_id=user_id,
        created_at=datetime.now(timezone.utc)
    )

    # 8. Persist the new record.
    db.session.add(log)
    db.session.commit()

    # 9. Return the created record with its generated database ID.
    return jsonify({
        "id": log.id,
        "user_id": log.user_id,
        "from_engine": log.from_engine,
        "to_engine": log.to_engine,
        "payload_id": log.payload_id,
        "created_at": log.created_at.isoformat()
    }), 201


@main_bp.route("/engine-logs/<int:log_id>", methods=["GET"])
@jwt_required
def get_engine_log(log_id: int):
    """
    Retrieve one EngineLog by ID, enforcing resource ownership.

    Authentication and ownership:
        Requires a valid JWT. The authenticated user's ID is supplied
        through g.user_id. The requested record must belong to that user.

    Processing:
        1. Look up the EngineLog by its primary key.
        2. Return the standard 404 response if no record exists.
        3. Return the same 404 response if another user owns the record.
        4. Serialize and return the record when ownership is confirmed.

    Args:
        log_id: The primary key of the EngineLog to retrieve.

    Returns:
        - 200 with the EngineLog when the authenticated user owns it.
        - 404 with the standard NOT_FOUND envelope when the record does
          not exist or belongs to another user.

    Security:
        Returning the same 404 response for missing and non-owned records
        prevents the endpoint from revealing another user's resource.
    """

    # 1. Look up the requested record by primary key.
    log = EngineLog.query.get(log_id)

    # 2. Return the standard response when the record does not exist.
    if log is None:
        return engine_log_not_found(log_id)

    # 3. Enforce ownership without revealing whether another user's record exists.
    if log.user_id != g.user_id:
        return engine_log_not_found(log_id)

    # 4. Return the record after ownership has been confirmed.
    return jsonify({
        "id": log.id,
        "user_id": log.user_id,
        "from_engine": log.from_engine,
        "to_engine": log.to_engine,
        "payload_id": log.payload_id,
        "created_at": log.created_at.isoformat(),
    }), 200


@main_bp.delete("/engine-logs/<int:log_id>")
@jwt_required
def delete_engine_log(log_id: int):
    """
    Delete one EngineLog by ID, enforcing resource ownership.

    Authentication and ownership:
        Requires a valid JWT. The authenticated user's ID is supplied
        through g.user_id. Only the owner may delete the requested record.

    Processing:
        1. Look up the EngineLog by its primary key.
        2. Return the standard 404 response if no record exists.
        3. Return the same 404 response if another user owns the record.
        4. Delete and commit the record when ownership is confirmed.

    Args:
        log_id: The primary key of the EngineLog to delete.

    Returns:
        - 204 with an empty response body when deletion succeeds.
        - 404 with the standard NOT_FOUND envelope when the record does
          not exist or belongs to another user.

    Security:
        Returning the same 404 response for missing and non-owned records
        prevents the endpoint from revealing another user's resource.
    """

    # 1. Look up the requested record by primary key.
    log = EngineLog.query.get(log_id)

    # 2. Return the standard response when the record does not exist.
    if log is None:
        return engine_log_not_found(log_id)

    # 3. Enforce ownership without revealing whether another user's record exists.
    if log.user_id != g.user_id:
        return engine_log_not_found(log_id)

    # 4. Delete the owned record and commit the database change.
    db.session.delete(log)
    db.session.commit()

    # 5. Return 204 No Content to confirm successful deletion.
    return "", 204



@main_bp.patch("/engine-logs/<int:log_id>")
@jwt_required
def update_engine_log(log_id: int):
    """
    Fully update an existing EngineLog by ID, enforcing resource ownership.

    Request Body:
        A JSON object containing all required fields:
            - from_engine
            - to_engine
            - payload_id

        All three fields are required and follow the same non-empty
        validation rules as the create endpoint. The user_id field is
        not accepted from the client and cannot be changed here.

    Authentication and ownership:
        Requires a valid JWT. The authenticated user's ID is supplied
        through g.user_id. Only the owner may update the requested record.

    Processing:
        1. Look up the EngineLog by its primary key.
        2. Return the standard 404 response if no record exists.
        3. Return the same 404 response if another user owns the record.
        4. Read and validate the JSON request body.
        5. Require a JSON object before accessing named fields.
        6. Validate all required fields.
        7. Apply the permitted field updates and commit the change.
        8. Return the updated record.

    Args:
        log_id: The primary key of the EngineLog to update.

    Returns:
        - 200 with the updated EngineLog when validation succeeds.
        - 400 with a VALIDATION_ERROR envelope when the body is missing,
          is not a JSON object, or fails field-level validation.
        - 404 with the standard NOT_FOUND envelope when the record does
          not exist or belongs to another user.

    Security:
        The ownership check occurs before request-body processing.
        Missing and non-owned records receive the same 404 response,
        preventing disclosure of another user's resource.
    """

    # 1. Look up the requested record by primary key.
    log = EngineLog.query.get(log_id)

    # 2. Return the standard response when the record does not exist.
    if log is None:
        return engine_log_not_found(log_id)

    # 3. Enforce ownership before processing the submitted request body.
    if log.user_id != g.user_id:
        return engine_log_not_found(log_id)

    # 4. Read the JSON request body.
    data = request.get_json()

    # 5. Reject a missing JSON body.
    if data is None:
        return engine_log_validation_error({
            "body": ["JSON body is required"]
        })

    # 6. Require a JSON object before accessing named fields.
    #    Valid JSON arrays and scalar values cannot be used as
    #    request objects and must not reach the field extraction below.
    if not isinstance(data, dict):
        return request_object_validation_error()

    # 7. Extract the required EngineLog fields.
    from_engine = data.get("from_engine")
    to_engine = data.get("to_engine")
    payload_id = data.get("payload_id")

    # 8. Collect field-level errors for missing or empty values.
    field_errors = {}
    if not from_engine:
        field_errors["from_engine"] = ["from_engine is required"]
    if not to_engine:
        field_errors["to_engine"] = ["to_engine is required"]
    if not payload_id:
        field_errors["payload_id"] = ["payload_id is required"]

    # 9. Return the validation response if any required fields are invalid.
    if field_errors:
        return engine_log_validation_error(field_errors)

    # 10. Apply the permitted updates to the existing owned record.
    log.from_engine = from_engine
    log.to_engine = to_engine
    log.payload_id = payload_id

    # 11. Persist the changes.
    db.session.commit()

    # 12. Return the updated record in the standard response shape.
    return jsonify({
        "id": log.id,
        "user_id": log.user_id,
        "from_engine": log.from_engine,
        "to_engine": log.to_engine,
        "payload_id": log.payload_id,
        "created_at": log.created_at.isoformat()
    }), 200


