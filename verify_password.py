from werkzeug.security import check_password_hash

stored_hash = "scrypt:32768:8:1$xO9jfPE9HqpBdrce$82f6696279dc3f7caad9a3e7a97b2e24e6d1ffdfd291f143517c55347e68f79610e1ea5a8b8b8eda0af37a8c6b8f8aef29aa4d2d051efa455a0fe12d87158000"

print(check_password_hash(stored_hash, "TestPassword123!"))  # expect True
print(check_password_hash(stored_hash, "WrongPassword"))     # expect False