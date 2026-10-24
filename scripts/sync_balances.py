"""Read real demo balances and publish snapshots to Person C; no money moves."""
import json
import httpx
from runway_money.backend import TrueMarketsBackend

backend = TrueMarketsBackend()
for name in ('test', 'test2'):
    rows = backend.balances(name)
    snapshot = {'label': f'{name} — real Gateway wallet', 'treasury_mode': 'pay_in_kind',
                'simulated': False, 'assets': [
                    {'asset': b['symbol'], 'amount': float(b['available']),
                     'usd_value': float(b['available']) if b['stable'] else None,
                     'chain': b['chain'], 'asset_id': b['asset_id']} for b in rows],
                'valuation_note': 'Stablecoins assume $1; nonstable USD values are omitted',
                'execution_hold': True}
    response = httpx.put(f'http://localhost:8000/balances/{name}', json=snapshot, timeout=10)
    response.raise_for_status()
    print(json.dumps({'agent': name, 'assets': snapshot['assets']}))
