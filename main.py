"""
Main Vercel Entrypoint for Multi-Engine Persistent Data Layer API
"""

from api.index import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
