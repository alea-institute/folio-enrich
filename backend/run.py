"""Entry point for standalone executable (PyInstaller)."""
import subprocess
import sys
import threading
import time
import webbrowser


def open_browser():
    time.sleep(2)
    webbrowser.open("http://localhost:8731")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8731)
