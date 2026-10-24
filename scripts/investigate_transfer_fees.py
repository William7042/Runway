"""Unsigned fee investigation only; no signing or execution operations."""
import json
import os
from decimal import Decimal
from pathlib import Path
from runway_money.backend import TrueMarketsBackend, public
from runway_money.preflight import SolanaPreflight, token_deltas


def main():
    backend = TrueMarketsBackend()
    buyer, seller = 'test', 'test2'
    assets = backend.assets()
    balances = backend.balances(buyer)
    asset = next(a for a in assets if a['id'] == next(
        b['asset_id'] for b in balances if b['symbol'] == 'PYUSD' and b['chain'] == 'solana'))
    wallet = next(w['address'] for w in backend.user(buyer)['wallets'] if w['chain_family'] == 'solana')
    recipient = backend.recipient(seller, 'solana')
    rows = []
    preflight = SolanaPreflight(os.getenv('RUNWAY_SOLANA_RPC', 'https://api.mainnet-beta.solana.com'))
    for amount in ('5', '6', '10'):
        prepared = backend.prepare_transfer(buyer, asset['id'], amount, recipient)
        reread = backend.call(buyer, 'GET', f'/v1/gateway/transfers/{prepared["id"]}')
        row = {'requested_gross': amount, 'prepared_fee': prepared['fee'],
               'prepared_received': prepared['received'], 'get_fee': reread['fee'],
               'get_received': reread['received'], 'status': reread['status'],
               'transfer_id': prepared['id']}
        try:
            evidence = preflight.inspect(prepared, wallet)
            simulation = evidence['_simulation']
            sent = -token_deltas(simulation, wallet).get(asset['address'], Decimal(0))
            received = token_deltas(simulation, recipient).get(asset['address'], Decimal(0))
            owners = set(x.get('owner') for field in ('preTokenBalances','postTokenBalances') for x in simulation[field])
            others = {owner: str(token_deltas(simulation, owner).get(asset['address'], Decimal(0)))
                      for owner in owners if owner not in {wallet, recipient}}
            row.update(simulated_sent=str(sent), simulated_received=str(received),
                       simulated_fee=str(sent-received), other_owner_deltas=others,
                       buyer_sol_delta=str(evidence['native_delta']),
                       network_fee_lamports=evidence['network_fee_lamports'])
        except ValueError as e:
            row['simulation_error'] = str(e)
        rows.append(row)
        print(json.dumps(row), flush=True)
    path = Path('.runway/transfer-fee-investigation.json')
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(rows, f, indent=2)


if __name__ == '__main__':
    main()
