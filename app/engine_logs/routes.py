"""
EngineLog feature blueprint and HTTP routes.

This module defines the EngineLog API endpoints and their shared
helpers. All routes are grouped under the /engine-logs URL prefix
through the engine_logs_bp blueprint.

Behavior and contracts:

- Authentication:
    All routes require a valid JWT. The jwt_required decorator
    establishes the authenticated identity through g.user_id.

- Ownership:
    EngineLog records are always associated with a user through
    EngineLog.user_id. Routes only operate on records owned by the
    authenticated user.

- URLs:
    - GET    /engine-logs
    - POST   /engine-logs
    - GET    /engine-logs/<int:log_id>
    - PATCH  /engine-logs/<int:log_id>
    - DELETE /engine-logs/<int:log_id>

The detailed behavior for listing, creating, retrieving, updating,
and deleting EngineLog records is preserved from the original
implementation in app.main.
"""

from flask import Blueprint, jsonify, request, g
from app.models import EngineLog
from app.extensions import db
from app.auth import jwt_required
import math
from datetime import datetime, timezone

from app.main import request_object_validation_error


# Blueprint for all EngineLog feature routes.
# Mounted at /engine-logs by create_app, so every route defined
# on this blueprint becomes part of the EngineLog API surface.
engine_logs_bp = Blueprint(
    "engine_logs",
    __name__,
    url_prefix="/engine-logs",
)

# Public paths handled by this blueprint:
# - GET    /engine-logs
# - POST   /engine-logs
# - GET    /engine-logs/<int:log_id>
# - PATCH  /engine-logs/<int:log_id>
# - DELETE /engine-logs/<int:log_id>


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
    # 1. Construct the shared NOT_FOUND envelope for EngineLog resources.
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

    This helper keeps request validation responses for EngineLog create,
    update, and list operations consistent.

    Args:
        details: A mapping of field or parameter names to lists of error
            messages describing the validation failures.

    Returns:
        A 400 response with the standard VALIDATION_ERROR envelope.
    """
    # 1. Wrap the supplied field-level errors in the shared envelope.
    return jsonify({
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid engine log data",
            "details": details,
        }
    }), 400

@engine_logs_bp.route("", methods=["POST"])
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

@engine_logs_bp.route("", methods=["GET"])
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

@engine_logs_bp.route("/<int:log_id>", methods=["GET"])
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

@engine_logs_bp.delete("/<int:log_id>")
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



@engine_logs_bp.patch("/<int:log_id>")
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

