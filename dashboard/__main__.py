"""Entry point: python -m dashboard"""
import sys
import os
import webbrowser
import threading

# Ensure project root is on path so retrieval imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def open_browser():
    import time
    time.sleep(1.5)
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        "dashboard.server:app",
        host="0.0.0.0",
        port=8501,
        reload=False,
        log_level="info",
    )
