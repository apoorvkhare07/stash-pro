"""
Minimal test settings that import from the main settings but override
the database to use in-memory SQLite and provide a hardcoded SECRET_KEY.
"""
import os

# Ensure SECRET_KEY is available before importing main settings
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")

from stash_pro.settings import *  # noqa: F401, F403

# Override database to use in-memory SQLite
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable throttling / pagination noise in tests
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_PAGINATION_CLASS": None,
    "PAGE_SIZE": None,
}
