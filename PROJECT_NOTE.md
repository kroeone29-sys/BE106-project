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
