"""Run-tagged Uvicorn host with a private file-based shutdown channel."""
from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

import uvicorn


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--validation-run-id", required=True)
    parser.add_argument("--shutdown-file", type=Path, required=True)
    args = parser.parse_args()
    config = uvicorn.Config("dtos_app:app", host="127.0.0.1", port=args.port)
    server = uvicorn.Server(config)

    def control() -> None:
        while not server.should_exit:
            if args.shutdown_file.exists():
                server.should_exit = True
                return
            time.sleep(.1)

    threading.Thread(target=control, name=f"dtos-validation-{args.validation_run_id}", daemon=True).start()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
