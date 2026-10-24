"""Stable Person A interface. Defaults to explicitly labeled simulation."""
import os
from dotenv import load_dotenv
from .stub import StubRouter
from .queue import HTTPQueue

load_dotenv()
_router = None


def configure(router):
    global _router
    _router = router


def get_router():
    global _router
    if _router is None:
        if os.getenv("RUNWAY_MODE", "stub") == "stub":
            _router = StubRouter(HTTPQueue(os.getenv("RUNWAY_QUEUE_URL", "http://localhost:8000")))
        else:
            from .router import build_router
            _router = build_router()
    return _router


def propose_payment(buyer, seller, amount_usd, purpose, source):
    return get_router().propose_payment(buyer, seller, amount_usd, purpose, source)


def execute(proposal_id):
    return get_router().execute(proposal_id)
