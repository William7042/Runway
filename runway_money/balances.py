"""Read-only live wallet snapshots, independent of payment execution."""
from datetime import datetime, timezone
import asyncio
import json
import logging
import os
import time
from pathlib import Path

from .backend import TrueMarketsBackend
from .state import State

logger=logging.getLogger(__name__)


def snapshot(backend, user, *, mode='pay_in_kind', held=False):
    rows=backend.balances(user)
    return {'label':f'{user} — real Gateway wallet','treasury_mode':mode,
        'simulated':False,'snapshot_at':datetime.now(timezone.utc).isoformat(),
        'assets':[{'asset':r['symbol'],'amount':float(r['available']),
            'usd_value':float(r['available']) if r['stable'] else None,
            'chain':r.get('chain'),'asset_id':r['asset_id']} for r in rows],
        'valuation_note':'Stablecoins assume $1; nonstable USD values are omitted',
        'execution_hold':held}


def sync(backend, publish, accounts):
    try:
        State().check_hold();held=False
    except RuntimeError:
        held=True
    errors={}
    for user in accounts.get('signer_files',{}):
        try:
            publish(user,snapshot(backend,user,mode=accounts.get('modes',{}).get(user,'pay_in_kind'),held=held))
        except Exception as exc:
            # Keep the last known snapshot and its timestamp; never fabricate zero balances.
            errors[user]=type(exc).__name__
    return errors


async def watch(publish, *, interval=5, backend_factory=TrueMarketsBackend, accounts_path=None):
    """No quotes, signing, orders, or transfers; no overlapping poll cycles."""
    backend=None
    path=Path(accounts_path or os.getenv('RUNWAY_ACCOUNTS_FILE','.runway/accounts.json'))
    while True:
        started=time.monotonic()
        try:
            if backend is None:
                backend=await asyncio.to_thread(backend_factory)
            accounts=json.loads(path.read_text())
            errors=await asyncio.to_thread(sync,backend,publish,accounts)
            if errors: logger.warning('Wallet snapshot refresh incomplete: %s',errors)
        except Exception as exc:
            logger.warning('Wallet snapshot refresh unavailable (%s)',type(exc).__name__)
        await asyncio.sleep(max(.1,interval-(time.monotonic()-started)))
