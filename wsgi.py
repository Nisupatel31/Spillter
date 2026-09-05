# WSGI entrypoint for PythonAnywhere, cPanel, and standard WSGI servers
import sys
import os

# Add project directory to sys.path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Initialize database tables on startup
from backend.database import init_db
init_db()

# Wrap ASGI FastAPI app into WSGI using a2wsgi
try:
    from a2wsgi import ASGIMiddleware
    from backend.main import app
    application = ASGIMiddleware(app)
except ImportError:
    from backend.main import app
    application = app
