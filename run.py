import os
import sys
import time
import webbrowser
import threading
import uvicorn

# Reconfigure stdout for utf-8 if supported
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def open_browser():
    time.sleep(1.2)
    url = "http://localhost:8000"
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Could not automatically open browser: {e}")
    print("\n=======================================================")
    print(f"Spillter App is running!")
    print(f"Opening in your browser: {url}")
    print("=======================================================\n")

if __name__ == "__main__":
    # Ensure project root is in sys.path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from backend.database import init_db
    init_db()

    # Launch browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run FastAPI server with auto-reload
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
