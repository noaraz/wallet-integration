"""Application entrypoint.

Phase 1 wires this into a real web server + telegram webhook handler.
For now it exposes a tiny `healthz()` used by the scaffold smoke test.
"""

from __future__ import annotations


def healthz() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    print(healthz())
