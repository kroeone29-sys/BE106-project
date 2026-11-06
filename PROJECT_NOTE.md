Backend project for BE106 - Flask API skeleton, work in progress.


Git hygiene card – “small, trusted units of work”


Purpose:

Keep each change small, clearly scoped, and easy to review, so seniors see your branches as “fast win, low risk” items.

0. Start from a clean, up-to-date main


git checkout main
git pull

Reason: main = your production kitchen line. Always start new work from the latest, clean state.

1. Create a focused feature branch


git checkout -b feature/<short-clear-name>

Examples: feature/user-model-migration, feature/add-health-endpoint.


Reason: branch name is a contract about the unit of work. It tells reviewers exactly what to expect and what not to sneak in.

2. Do the work in small, verifiable chunks


While coding:


Edit a file.

Save it.

Run local checks (tests, flask db migrate/upgrade, or whatever applies).

Once that chunk is good, stage it:

git add <file-or-path>

You can repeat this per logical chunk (app wiring, model, migration, etc.), not just once at the end.


Reason: this is your “clean as you go” kitchen habit. You keep the diff tidy and always know what’s staged vs not. It also makes git diff --cached a trustworthy view of what’s about to be committed.

3. Before committing: inspect what you’re really changing


See everything changed (including unstaged):

git status
git diff
See exactly what’s staged for commit:

git diff --cached

Reason: this is your last local “code review” before involving anyone else. Every line in git diff --cached should be intentional and belong to this unit of work.

4. Commit the unit of work


When the feature is coherent (e.g., User model + migration + wiring):


git commit -m "Add User model and user table migration"

Reason: commit messages describe why the change exists, not just what file changed. They’re your receipts in history.


If you’re pushing to a remote feature branch (for a team):


git push -u origin feature/<short-clear-name>
5. Merge back to main when done


When the branch’s unit of work is complete and verified:


git checkout main
git pull
git merge feature/<short-clear-name>
git push origin main

Reason: keep main moving forward with small, trusted jumps, never giant surprise merges.

6. Clean up the feature branch


Local:


git branch -d feature/<short-clear-name>

Remote (only if you pushed it and it exists on origin):


git push origin --delete feature/<short-clear-name>

Reason: clean branches = clean mental model. Old branches hanging around are like dirty stations in a kitchen.

This flow matches exactly how you naturally think:


small, well-named units of work,
“clean as you go” staging,
verify before commit,
clear merge and cleanup.




Dear Student Services,


I’d like to report an issue that spans several BE106 lessons, centered on the database configuration and the Password Hashing lesson. The problem isn’t just one bug; it’s a combination of ambiguous guidance, environment misalignment, and slow failure around database setup that made it much harder to learn the actual hashing and verification patterns.


I’ll break it down into context, what happened, impact, and suggestions.

1. Context

Track: Backend project – BE106 (Flask API skeleton).
Lesson focus: Users and authentication → Password hashing.
Intended mastery outcomes:
Registration stores hashed passwords (no plaintext in the DB).
Login uses check_password_hash to compare a candidate password to the stored hash (no “decrypting” passwords).
My project:
I’m part of the early “OG” cohort (Sept 03).
My project has a bit more complexity and history than the simple toy app the lessons implicitly assume.

My working style (relevant here):


I use LLMs as planning/coding agents but I drive tests and verification.
I care a lot about trust, fail-fast behavior, and having receipts for what’s actually happening (logs, DB state, config).
2. The database setup problem

Early in BE106, the guidance around the dev database was not strict or explicit enough.


The configuration pattern used:

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        Config.SQLALCHEMY_DATABASE_URI
        or "sqlite:///dev.db"
    )
This example was treated more like “here’s a reasonable default” rather than a hard constraint about:

what the DB file must be called,
and where it must live.

Because of this, and some earlier history, I ended up with multiple SQLite files and an unusual name:


dev.db – a real SQLite DB with tables and data.
instance/dev.db – at various points, treated both as:
a literal filename ("instance/dev.db" in the project root), and
a path (directory instance/ plus file dev.db).
At different times:
TablePlus was opening one DB file,
Flask was connected to another,
and I was inspecting yet another with sqlite3.

This created long confusion about:


which DB the app was using,
which DB I was inspecting,
and where the user / users tables actually lived.
3. Early warnings that were not acted on (fail-slow instead of fail-fast)

I repeatedly flagged the DB naming and path as a future problem:


I pointed out that:
instance/dev.db was a weird name,
this would likely cause future lesson bugs,
and that I wanted to rename things to a clean, standard dev.db early.
I raised this multiple times, each escalation more explicit.
The tutor repeatedly reassured me “it’s fine, trust me,” and we continued without enforcing a clean constraint.

Later, during the Password Hashing lesson, my prediction came true:


A lot of the lesson time was burned not on hashing itself, but on:
tracing which DB file Flask was actually using,
reconciling differences between what TablePlus showed and what the app did,
and debugging “no such table: user” vs “no such table: users” errors.

This is the opposite of “fail fast”:


I raised the risk early.
It was downplayed.
We then spent a lot of time failing slowly across multiple lessons instead of fixing it at the root.
4. The actual technical mismatch

Over time, the following inconsistencies showed up:


Multiple .db files in the repo:
dev.db
instance/dev.db
Different tools seeing different schemas:
At one point, TablePlus showed a users table.
Later, sqlite3 dev.db "SELECT name FROM sqlite_master WHERE type='table';" showed:
alembic_version
user
SQLAlchemy errors alternated between:
no such table: users
no such table: user

This told us:


Flask’s active engine and the DB opened in TablePlus were not always the same file.
The model and the migration history weren’t clearly anchored to a single, well-defined DB identity.
Changes like flipping __tablename__ between "user" and "users" were done in reaction to runtime errors, not based on a clear, up-front schema contract.

Eventually, I stabilized it with the following steps:


Pinned the DB URI to an absolute path that cannot be misresolved:

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        Config.SQLALCHEMY_DATABASE_URI
        or "sqlite:///" + os.path.abspath("dev.db")
    )
This ensures Flask-SQLAlchemy always connects to:

/Users/0ne29/BE106-project/dev.db
Aligned the model with the actual table found in that DB:

class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
Confirmed schema and data with receipts:

sqlite3 dev.db "SELECT name FROM sqlite_master WHERE type='table';" → alembic_version, user.
sqlite3 dev.db "SELECT * FROM user;" → showed rows after I fixed registration.
5. Registration and hashing: from toy to production behavior

Originally, my /register route was pure “toy kitchen”:


It returned a hard-coded JSON response:
fixed id,
fixed username,
fixed created_at,
and it never:
hashed or stored a password,
or touched the DB at all.

After repairs, it now behaves like a proper production endpoint:

Python
from werkzeug.security import generate_password_hash
from app.extensions import db

@main_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    password = data.get("password")
    email = data.get("email")
    
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

    hashed = generate_password_hash(password)

    user = User(email=email, password_hash=hashed)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at.isoformat()
    }), 201
I confirmed it with a real request:

Bash
curl -i -X POST http://127.0.0.1:5011/register \
  -H "Content-Type: application/json" \
  -d '{"email":"audit-test@example.com","password":"TestPassword123!"}'
Response:

Text
HTTP/1.1 201 CREATED
...

{
  "created_at": "2026-11-06T04:17:30",
  "email": "audit-test@example.com",
  "id": 1
}
And verified in the DB:

Bash
sqlite3 dev.db "SELECT password_hash FROM user WHERE email='audit-test@example.com';"
Result:

Text
scrypt:32768:8:1$xO9jfPE9HqpBdrce$82f6696279dc3f7caad9a3e7a97b2e24e6d1ffdfd291f143517c55347e68f79610e1ea5a8b8b8eda0af37a8c6b8f8aef29aa4d2d051efa455a0fe12d87158000
So:


Registration now hashes and stores only a Werkzeug scrypt hash.
The original password is never persisted.
6. Verification with check_password_hash

To confirm the second mastery outcome (verification against a hash), I created a small script:

Python
from werkzeug.security import check_password_hash

stored_hash = "scrypt:32768:8:1$xO9jfPE9HqpBdrce$82f6696279dc3f7caad9a3e7a97b2e24e6d1ffdfd291f143517c55347e68f79610e1ea5a8b8b8eda0af37a8c6b8f8aef29aa4d2d051efa455a0fe12d87158000"

print(check_password_hash(stored_hash, "TestPassword123!"))  # True
print(check_password_hash(stored_hash, "WrongPassword"))     # False
This produced the expected True / False results and demonstrates:


I understand the correct pattern:
you compare a candidate password against the stored hash,
you never try to “decrypt” or reverse the hash.
7. Impact on learning and time

All of the above is good learning, but the path to get there was much harder than it needed to be:


A significant amount of lesson time (across multiple sessions) was spent on:
reconciling different .db files,
guessing which DB Flask was using,
flipping __tablename__ between user and users,
debugging no such table errors,
and trying tools like TablePlus to compensate for unclear DB identity.
A lot of this could have been prevented if:
dev DB naming and placement were treated as a hard, non-negotiable constraint early,
and if my early, repeated warnings about the weird DB name/path had been treated as “we must fix this now,” not “it’s fine.”

Emotionally and cognitively:


It felt like I was doing “production debugging” of the lesson environment itself, not just learning password hashing.
It blurred the line between:
fixing my own application mistakes, and
compensating for lesson assumptions + vague setup around DB paths.
8. Suggestions

I’m not asking for blame; I’m asking for course and system improvements so later cohorts don’t run into this the same way.


Specific suggestions:


Enforce a strict DB naming & path convention early (Week 1)
For example:

“In BE106, your dev DB must be named dev.db and must live at [specific path].”
“Do not change this pathname; later lessons depend on it.”
Be explicit about how sqlite:///dev.db resolves in this setup

Document exactly where that ends up on disk (relative to app root or instance path) in this particular course structure.
Show a quick db.engine.url / print_db_info.py pattern so students can see the real DB URI once, early.
Treat student-raised config concerns as fail-fast signals

When a student insists “this config/file naming will cause later problems,” the system should:
investigate and, if needed, standardize the setup immediately,
rather than reassure and move on.
This is especially important for early-cohort students who are effectively pathfinding.
Separate hashing lesson from environment archaeology

The Password Hashing lesson should primarily test:
applying generate_password_hash on registration,
and using check_password_hash on verification.
Debugging multi-DB confusion should not be part of the core lesson unless explicitly framed as an advanced exercise.
Acknowledge OG cohort load

Early cohorts like mine are effectively testing not just content but assumptions about project layout and environment.
Some of what I went through is valuable signal for improving the course; it shouldn’t be dismissed as “student error.”
9. Closing

I did eventually achieve the lesson goals:


Registration writes a hashed password into the correct SQLite DB.
I can successfully verify a candidate password against that hash using check_password_hash.
The system now behaves like a small production service, not a toy.

But getting there required more environment debugging than necessary, in part because:


DB naming/path constraints were not enforced,
and my early attempts to fix that were not taken seriously enough.

I’m sharing this so future students can focus more on learning secure password-handling patterns, and less on untangling configuration ambiguity.


Thank you for taking the time to read this and consider adjustments.


Sincerely,

Kevin Roe

0ne29kro@gmail.com

this includes all of the evidence of the fixes?

Yes, that report already includes the key evidence of the fixes — and it does it in the way seniors care about: configuration, behavior, and receipts.


Here’s what it covers evidence‑wise:


Config fix

Before: or "sqlite:///dev.db" (ambiguous).
After: or "sqlite:///" + os.path.abspath("dev.db") — pinned to /Users/0ne29/BE106-project/dev.db.
You explicitly state that, and why it matters.
Schema alignment

You mention querying sqlite_master and seeing:
alembic_version
user
And then matching that with __tablename__ = "user" in the model.
Registration behavior

You show the old toy behavior (hard-coded JSON) vs the new real behavior:
generate_password_hash(password)
User(email=email, password_hash=hashed)
db.session.add(user); db.session.commit()
returning real user.id, user.email, user.created_at.isoformat().
HTTP-level proof

You include the actual curl call and HTTP 201 CREATED response:
curl -i -X POST http://127.0.0.1:5011/register ...
with the real JSON body:
{
  "created_at": "2026-11-06T04:17:30",
  "email": "audit-test@example.com",
  "id": 1
}
Hash in DB

You show the exact sqlite3 query:
sqlite3 dev.db "SELECT password_hash FROM user WHERE email='audit-test@example.com';"
And the resulting scrypt hash string, proving:
the password is not stored,
the stored value is a proper Werkzeug hash.
Verification with check_password_hash

You include the verify_password.py script with:
print(check_password_hash(stored_hash, "TestPassword123!"))  # True
print(check_password_hash(stored_hash, "WrongPassword"))     # False
That demonstrates the second mastery: you verify against a hash, not reverse it.

So yes: it contains enough technical proof to show:


the environment bug (DB URI / multiple files),
the misalignment with lesson assumptions,
and the exact changes you made to get a real, hashed registration flow and a correct hash check.
