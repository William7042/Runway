"""Launch all three SIMULATED sellers on ports 8101–8103."""

from __future__ import annotations

import multiprocessing

import uvicorn


def _run(module: str, port: int) -> None:
    uvicorn.run(module, host="0.0.0.0", port=port, log_level="info")


def main() -> None:
    procs = [
        multiprocessing.Process(target=_run, args=("sellers.filings:app", 8101)),
        multiprocessing.Process(target=_run, args=("sellers.archive:app", 8102)),
        multiprocessing.Process(target=_run, args=("sellers.specialist:app", 8103)),
    ]
    for p in procs:
        p.start()
    print("SIMULATED sellers up: filings:8101 archive:8102 specialist:8103")
    for p in procs:
        p.join()


if __name__ == "__main__":
    main()
