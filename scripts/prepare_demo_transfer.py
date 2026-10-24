"""Unsigned fee check only. Never imports or calls a signing/execute operation."""
import json
import argparse
from decimal import Decimal
from pathlib import Path
from runway_money.client import RunwayClient, TrueMarketsError

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--amount', default='1')
amount = Decimal(parser.parse_args().amount)
if not amount.is_finite() or not 0 < amount <= 5:
    raise SystemExit('Unsigned probe supports positive amounts up to 5 only')

with RunwayClient() as client:
    buyer = client.lookup_user('test')
    recipient = client.lookup_user('test2')
    address = next(w['address'] for w in recipient['wallets'] if w['chain_family'] == 'solana')
    balances = client.request('GET', '/v1/gateway/balances', user_id=buyer['user_id'])['data']
    held = next(b for b in balances if b['stable'] and b['chain'] == 'solana' and float(b['available']) >= 1)
    try:
        prepared = client.request('POST', '/v1/gateway/transfers', user_id=buyer['user_id'], body={
            'asset_id': held['asset_id'], 'qty': str(amount), 'qty_unit': 'base', 'to': address})
    except TrueMarketsError as e:
        print(json.dumps({'http_status': e.status_code, 'category': e.category,
                          'code': e.code, 'message': e.api_message,
                          'metadata': e.metadata, 'request_id': e.request_id}, indent=2))
        raise SystemExit(1)
    path = Path('.runway/unsigned_demo_transfer.json')
    path.write_text(json.dumps(prepared, indent=2)); path.chmod(0o600)
    print(json.dumps({k: v for k,v in prepared.items() if k not in {'payloads','web_authn_payload'}}, indent=2))
    print('Unsigned payload count:', len(prepared.get('payloads', [])))
