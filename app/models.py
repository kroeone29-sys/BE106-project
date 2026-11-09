"""
Database models for the authentication system.

This module defines the User model, which represents
an authenticated account
in the application. The User's `role` field controls
authorization for
admin-only endpoints:

- authentication: a valid JWT proves which User is making the 
request
- authorization: the User.role value (e.g. "user" or "admin")
gated access to protected routes
    
Routes must never trust client-submitted roles; they read the role from
the verified User record or token claims instead.
 """


from app.extensions import db

class User(db.Model):
    """Application user account with role-based authorization.

    Attributes:
        id: Primary key.
        email: Unique login identifier for the user.
        password_hash: Hashed password for authentication.
        role: Authorization role for this user. Defaults to "user" and is
            used to gate admin-only routes. Valid roles are currently
            "user" and "admin".
    """

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    display_name = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="user")