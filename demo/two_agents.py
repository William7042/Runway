"""Two real model conversations, paid through the existing human approval queue.

The service can execute only its own externally approved proposal. It has no
approval endpoint. Jobs are bound to a persisted proposal and delivered once.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import llm
from agent.payments import propose_and_enqueue
from agent.policy import PolicyConfig
from runway_money import get_router

ROOT = Path(__file__).resolve().parents[1]
BRIEF = """Runway is a hackathon project. Agents have True Markets wallets and
purchase specialist work. A buyer requests a proposal, a deterministic router
prices supported assets, an independent verifier flags mismatches, and a human
approves EVERY order in a queue before local signing. The router simulates
Solana transactions and confirms transfers. Seller test2 accepts PYUSD from
buyer test. This specialist review costs $4 net with a separately disclosed $1
transfer fee ($5 total). DRY_RUN never signs. Tokenized stocks are optional.
This brief is the only project evidence supplied; do not invent market data,
web searches, test results, or verified security guarantees."""


class Runs:
    def __init__(self, root=ROOT / '.runway' / 'agent-runs'):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.active = False

    def read(self, ident):
        # UUID validation also prevents arbitrary file reads.
        ident = str(uuid.UUID(ident))
        with self.lock:
            return json.loads((self.root / (ident + '.json')).read_text())

    def save(self, run):
        with self.lock:
            target = self.root / (run['id'] + '.json')
            temp = target.with_suffix('.tmp')
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                json.dump(run, f)
            os.replace(temp, target)

    def event(self, run, actor, text, status=None):
        run['events'].append({'actor': actor, 'text': text, 'time': time.time()})
        if status:
            run['status'] = status
        self.save(run)


def require_paid(run, proposal, receipt):
    """Approval alone cannot unlock paid specialist work."""
    if (proposal.get('id') != run['proposal_id'] or proposal.get('buyer') != 'test'
            or proposal.get('seller') != 'test2' or Decimal(str(proposal.get('amount_usd'))) != Decimal('4')
            or proposal.get('source') != 'user:two-agents:' + run['id']
            or proposal.get('status') != 'executed' or receipt.get('status') != 'executed'
            or not receipt.get('tx_hash')):
        raise ValueError('Confirmed payment bound to this job is required')
    quality = (receipt.get('fill') or {}).get('execution_quality', {})
    expected = Decimal(str(quality.get('expected_received', 0)))
    if (expected <= 0 or Decimal(str(quality.get('actual_received', 0))) < expected
            or Decimal(str(quality.get('shortfall', 0))) != 0
            or quality.get('needs_reconciliation')):
        raise ValueError('Specialist must receive the complete invoice')


def work(run, store, *, router=None, sleep=time.sleep, chat=None, enqueue=None):
    chat = chat or llm.chat
    enqueue = enqueue or propose_and_enqueue
    try:
        if os.getenv('RUNWAY_MODE') != 'live':
            raise ValueError('This demo requires RUNWAY_MODE=live; no simulated payments')
        store.event(run, 'Buyer · test', 'Planning a specialist review with the configured model.', 'planning')
        plan = llm.extract_json(chat([
            {'role': 'system', 'content': 'You are Runway buyer agent test. Write a concise plan and payment purpose for hiring specialist test2 to answer the user. Fixed invoice $4, transfer fee $1, total $5. You cannot change recipients or approve payments. Return JSON with plan and purpose strings.'},
            {'role': 'user', 'content': run['question']},
        ], json_mode=True, require_live=True))
        purpose = str(plan['purpose'])[:600]
        store.event(run, 'Buyer · test', str(plan['plan'])[:1500])
        router = router or get_router()
        policy = PolicyConfig(agent_id='two-agent-buyer', max_single_payment_usd=4,
                              spend_cap_usd=5, asset_allowlist={'PYUSD'},
                              recipient_allowlist={'test2'}, transfer_fee_budget_usd=1)
        proposal, checked, verifier = enqueue(buyer='test', seller='test2', amount_usd=4,
            purpose=purpose, source='user:two-agents:' + run['id'], user_request=run['question'],
            policy=policy, preferred_asset='PYUSD')
        if proposal is None:
            raise ValueError('Policy blocked: ' + '; '.join(checked.reasons))
        run['proposal_id'] = proposal.id
        store.event(run, 'Verifier', f'{verifier.verdict}: {verifier.reason}')
        store.event(run, 'Human approval', 'Review the proposal in Approval desk: $4 specialist + $1 fee = $5 total. Nothing is signed yet.', 'awaiting_approval')
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            p = router.queue.get(proposal.id)
            if p and p['status'] in {'rejected', 'failed'}:
                store.event(run, 'Human approval', 'Payment rejected or failed. No specialist work purchased.', p['status'])
                return
            if p and p['status'] == 'approved':
                store.event(run, 'Money router', 'Human approved. Simulating and executing the exact payment.', 'paying')
                receipt = router.execute(proposal.id)
                run['receipt'] = receipt
                store.save(run)
                if receipt['status'] == 'approved' and not receipt.get('tx_hash'):
                    store.event(run, 'Money router', 'DRY RUN: preview only; no payment or paid work delivered.', 'dry_run')
                    return
                p = router.queue.get(proposal.id)
                require_paid(run, p, receipt)
                break
            sleep(2)
        else:
            store.event(run, 'Human approval', 'Approval wait expired. No automatic retry or signing.', 'expired')
            return
        deliver(run, store, router=router, chat=chat)
    except Exception as exc:
        # SDK exception strings can contain request data. Never publish them.
        run['error_type'] = type(exc).__name__
        message = 'Run stopped. Check policy or payment receipt; no automatic payment retry.'
        if getattr(exc, 'status_code', None) in {400, 401, 403}:
            message = 'Model API rejected the request. Check the saved API key, credits, and model access. No automatic payment retry.'
        store.event(run, 'Service', message, 'failed')
    finally:
        with store.lock:
            store.active = False


def deliver(run, store, *, router, chat):
    # Validate again immediately before either paid model call. Delivery retry
    # uses the same confirmed receipt and never calls execute a second time.
    require_paid(run, router.queue.get(run['proposal_id']), run['receipt'])
    if not run.get('specialist_answer'):
        store.event(run, 'Specialist · test2', 'Payment confirmed. Reviewing the project with the configured model.', 'working')
        run['specialist_answer'] = chat([
            {'role': 'system', 'content': 'You are specialist agent test2. Answer the buyer question using only the supplied project brief. Be practical, concise, and honest about unverified details. Never request payments or claim web access.\n' + BRIEF},
            {'role': 'user', 'content': run['question']},
        ], require_live=True)
        store.event(run, 'Specialist · test2', run['specialist_answer'])
    run['answer'] = chat([
        {'role': 'system', 'content': 'You are buyer agent test. Summarize the paid specialist response for the human in under 220 words. Preserve caveats. No invented facts.'},
        {'role': 'user', 'content': 'Question: ' + run['question'] + '\nSpecialist: ' + run['specialist_answer']},
    ], require_live=True)
    store.event(run, 'Buyer · test', run['answer'], 'complete')


store = Runs()
app = FastAPI(title='Runway two-agent demo')
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173'],
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


class Request(BaseModel):
    question: str = Field(min_length=8, max_length=3000)


def has_key():
    return bool(llm.configuration()[1])


@app.get('/health')
def health():
    return {'key_configured': has_key(), 'model': llm.configuration()[2], 'provider': llm.configuration()[0],
            'mode': os.getenv('RUNWAY_MODE', 'stub'), 'dry_run': os.getenv('DRY_RUN', '1') != '0'}


@app.get('/runs')
def runs():
    with store.lock:
        paths = sorted(store.root.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
        return [json.loads(p.read_text()) for p in paths]


@app.get('/runs/{ident}')
def get_run(ident: str):
    try:
        return store.read(ident)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, 'Run not found')


@app.post('/runs', status_code=202)
def start(request: Request):
    if not has_key():
        raise HTTPException(503, 'Save a Claude or xAI API key in .env first')
    with store.lock:
        if store.active:
            raise HTTPException(409, 'A run is active. Finish or reject its payment first.')
        # Never silently abandon an unfinished run after a server restart.
        if any(r['status'] in {'planning', 'awaiting_approval', 'paying', 'working'} for r in runs()):
            raise HTTPException(409, 'An unfinished run exists; inspect it before creating another payment.')
        run = {'id': str(uuid.uuid4()), 'question': request.question, 'status': 'starting',
               'events': [], 'proposal_id': None, 'receipt': None, 'answer': None}
        store.save(run)
        store.active = True
        threading.Thread(target=work, args=(run, store), daemon=True).start()
        return run


@app.post('/runs/{ident}/retry-delivery')
def retry_delivery(ident: str):
    run = get_run(ident)
    with store.lock:
        if store.active or run['status'] == 'complete':
            raise HTTPException(409, 'Run active or already delivered')
        try:
            router = get_router()
            require_paid(run, router.queue.get(run['proposal_id']), run['receipt'] or {})
        except Exception:
            raise HTTPException(409, 'A confirmed payment is required; this endpoint never pays')
        store.active = True
    def retry():
        try:
            deliver(run, store, router=router, chat=llm.chat)
        except Exception as exc:
            run['error_type'] = type(exc).__name__
            store.event(run, 'Service', 'Delivery failed. You may retry delivery without paying again.', 'failed')
        finally:
            with store.lock:
                store.active = False
    threading.Thread(target=retry, daemon=True).start()
    return run
