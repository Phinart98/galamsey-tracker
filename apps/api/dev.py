"""Local development launcher.

psycopg-async requires asyncio's SelectorEventLoop. Windows defaults to
ProactorEventLoop (since Python 3.8), which makes every DB call raise
`InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`.

Setting the policy in main.py is too late: uvicorn creates its event loop
before importing the app module. So we set the policy here, then call
uvicorn.run(). Production deploys (Linux Cloud Run) can keep using
`uvicorn main:app` directly because Linux already uses SelectorEventLoop.

Run with: `uv run python dev.py`
"""

import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
    )
