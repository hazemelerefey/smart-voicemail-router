"""Run the Phase 1 API: python -m svr (from the repo root)."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("svr.api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
