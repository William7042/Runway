"""CLI deliberately has no approve or auto-approve command."""
import argparse
import json
import os
from pathlib import Path
from . import get_router
from .backend import TrueMarketsBackend


def setup_demo():
    backend = TrueMarketsBackend()
    assets = backend.assets()
    balance = backend.balances('test')
    seller = backend.user('test2')
    # Pay in kind using an actually held stablecoin on the receiver's chain.
    held = next(b for b in balance if b['stable'] and float(b['available']) >= 1 and b['chain'] == 'solana')
    asset = next(a for a in assets if a['id'] == held['asset_id'])
    config = {'signer_files': {
        'test': './truemarkets-test-signer-key-test.json',
        'test2': './truemarkets-test-signer-key-test2.json'},
        'sellers': {'test2': {'accepted_asset_ids': [asset['id']]}},
        'modes': {'test': 'pay_in_kind'}}
    path = Path('.runway/accounts.json')
    path.parent.mkdir(exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(config, f, indent=2)
    return {'buyer': 'test', 'seller': 'test2', 'asset': asset['symbol'],
            'chain': asset['chain'], 'available': held['available'],
            'recipient': next(w['address'] for w in seller['wallets'] if w['chain_family'] == 'solana'),
            'config': str(path), 'dry_run': os.getenv('DRY_RUN', '1') != '0'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('setup-demo')
    propose = sub.add_parser('propose')
    propose.add_argument('--buyer', required=True)
    propose.add_argument('--seller', required=True)
    propose.add_argument('--amount', required=True)
    propose.add_argument('--purpose', required=True)
    propose.add_argument('--source', required=True)
    execute = sub.add_parser('execute')
    execute.add_argument('proposal_id')
    sub.add_parser('wallet').add_argument('name')
    args = parser.parse_args()
    try:
        if args.command == 'setup-demo':
            result = setup_demo()
        elif args.command == 'propose':
            result = get_router().propose_payment(args.buyer, args.seller, args.amount, args.purpose, args.source)
        elif args.command == 'execute':
            result = get_router().execute(args.proposal_id)
        else:
            result = get_router().create_wallet(args.name)
        print(json.dumps(result, indent=2))
    except Exception as e:
        # Avoid leaking httpx request headers, SDK responses, or signer material.
        print(json.dumps({'error_type': type(e).__name__, 'message': 'Operation stopped. Check queue status and local plan; never retry an uncertain submission.'}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
