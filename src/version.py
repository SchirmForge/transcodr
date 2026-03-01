"""Application version and DB compatibility constants."""

APP_VERSION = "0.4.3"

# Set of app versions whose DB schema is compatible with the current schema.
# When a future release has breaking DB changes, reset this to only the new version.
DB_COMPATIBLE_VERSIONS: set[str] = {"0.4.3"}
