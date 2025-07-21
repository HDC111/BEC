import os
from superset.config import *  # Optional, but only if you want to extend the base config
from flask_login import current_user


FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": False
}
# Superset secret key (used for sessions)
SECRET_KEY = os.environ.get(
    "SUPERSET_SECRET_KEY",
    "4rkmJRkC62H6jpnApoXYQFm6B-5jE6AoW09dKkNoIM4m4Xhyshel5sQkbCmXuRkvLuPSPyOfUs6Z_LXmZCz_lw"
)

SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://superset_user_fti:admin123@localhost:5432/superset_fti"

# Timeout in seconds for SQL Lab queries
SQLLAB_ASYNC_TIME_LIMIT_SEC = 300
SQLLAB_TIMEOUT = 300

# Maximum rows to fetch
#SQL_MAX_ROW = 100000

#metadata and chart caching
CACHE_CONFIG = {
    "CACHE_TYPE": "FileSystemCache",
    "CACHE_DIR": os.path.join(os.path.dirname(__file__), "cache"),
    "CACHE_DEFAULT_TIMEOUT": 86000
}

DATA_CACHE_CONFIG = CACHE_CONFIG
'''
# Optional: Disable rate limits for dev use
ENABLE_PROXY_FIX = True

SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = True
TALISMAN_ENABLED = False


'''