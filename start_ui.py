"""Anchor Chat UI başlatıcı."""
import sys
sys.path.insert(0, "/workspace/anchor/src")

import uvicorn
from anchor.ui.app import app

if __name__ == "__main__":
    print("⚓ Anchor Chat UI: http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
