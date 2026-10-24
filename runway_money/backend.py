"""True Markets boundary. Preparation is unsigned; submission requires a guard."""
import hashlib
import json
import os
import time
from decimal import Decimal
from pathlib import Path
from .client import RunwayClient
from .treasury import dec


def dry_run():
    # Only the exact value 0 enables real execution. Malformed settings stay safe.
    return os.getenv('DRY_RUN', '1') != '0'


def public(data):
    """Do not put signing payloads into shared proposals, receipts, or logs."""
    return {k: v for k, v in data.items()
            if k not in {'payloads', 'web_authn_payload', 'signatures'}}


class TrueMarketsBackend:
    def __init__(self, client=None, signer_files=None, asset_metadata=None):
        self.client = client or RunwayClient()
        self.signer_files = signer_files or {}
        self.users = {}
        self.asset_metadata = asset_metadata or {}

    def user(self, name):
        if name not in self.users:
            self.users[name] = self.client.lookup_user(name)
        return self.users[name]

    def call(self, buyer, method, path, body=None, params=None):
        return self.client.request(method, path, user_id=self.user(buyer)['user_id'],
                                   body=body, params=params)

    def assets(self):
        page = self.client.request('GET', '/v1/gateway/assets')
        assets = list(page['data'])
        cursor = page.get('pagination', {}).get('next_cursor')
        while cursor:
            page = self.client.request('GET', '/v1/gateway/assets', params={'cursor': cursor})
            assets.extend(page['data'])
            cursor = page.get('pagination', {}).get('next_cursor')
        for asset in assets:
            # Explicit mapping supplies the underlying stock ticker; never infer
            # a tradable token or substitute a different chain/asset identifier.
            reference = self.asset_metadata.get(asset['id'], {}).get('reference_symbol')
            if reference:
                asset['reference_symbol'] = reference
        return assets

    def balances(self, buyer):
        return self.call(buyer, 'GET', '/v1/gateway/balances')['data']

    def recipient(self, seller, chain):
        family = 'solana' if chain == 'solana' else 'evm'
        wallets = self.user(seller)['wallets']
        return next(w['address'] for w in wallets if w['chain_family'] == family)

    def history(self, buyer):
        items = []
        cursor = None
        while True:
            page = self.call(buyer, 'GET', '/v1/defi/core/history',
                             params={'limit': 100, **({'cursor': cursor} if cursor else {})})
            items.extend(page.get('items', []))
            cursor = page.get('next_cursor')
            if not cursor:
                break
        # Older history only gives an amount and symbol, with no acquisition
        # value/fees. Never guess cost basis from those rows.
        required = {'asset_id', 'action', 'quantity', 'value_usd', 'fee_usd', 'timestamp'}
        if any(not required <= set(row) for row in items):
            raise ValueError('API history lacks complete acquisition values; endowment is blocked')
        return items

    def quote(self, buyer, source, target, quantity):
        if source['chain'] != target['chain'] or source.get('venue') != 'defi' or target.get('venue') != 'defi':
            raise ValueError('Cross-chain/CeFi payment paths are not supported in this demo')
        if source.get('stable') and not target.get('stable'):
            base, quote, side = target, source, 'buy'
        elif target.get('stable') and not source.get('stable'):
            base, quote, side = source, target, 'sell'
        else:
            raise ValueError('Only stablecoin/token swaps are supported; use pay in kind otherwise')
        if not base.get('tradeable') or base.get('type', 'spot') != 'spot':
            raise ValueError('Asset is not an active tradable spot market')
        body = {'chain': base['chain'], 'base_asset': base['address'],
                'quote_asset': quote['address'], 'order_side': side,
                'qty': str(quantity), 'qty_unit': 'quote' if side == 'buy' else 'base',
                'order_type': 'market'}
        result = self.call(buyer, 'POST', '/v1/defi/core/quote', body)
        if result.get('issues'):
            raise ValueError('True Markets quote has issues; review the account before paying')
        if result.get('quote_asset') != quote['address'] or result.get('base_asset') != base['address']:
            raise ValueError('Quote changed the settlement asset; bridge requires a separate reviewed plan')
        if result.get('bridge_state'):
            raise ValueError('Bridge is not represented in the approved payment path')
        if result.get('fee_asset') != quote['address']:
            raise ValueError('Fee denomination is not the planned quote asset')
        output = dec(result['qty_out'])
        if output <= 0:
            raise ValueError('Quote has no output')
        return {'input': str(quantity), 'output': str(output), 'fee': result['fee'],
                'fee_asset_id': quote['id'], 'raw': public(result),
                'order_body': {'asset_id': base['id'], 'qty': str(quantity),
                               'qty_unit': 'quote' if side == 'buy' else 'base',
                               'side': side, 'type': 'market', 'venue': 'defi'}}

    def prepare_order(self, buyer, quote):
        # This endpoint can execute CeFi orders immediately: force DeFi only.
        body = quote['order_body']
        if body.get('venue') != 'defi':
            raise ValueError('Live orders must use unsigned DeFi preparation')
        return self.call(buyer, 'POST', '/v1/gateway/orders', body)

    def limit_preview(self, buyer, asset, stable, quantity, price):
        """CeFi has a nonbinding compute_quote; DeFi limit support varies."""
        if asset.get('venue') != 'cefi' or stable.get('venue') != 'cefi':
            raise ValueError('This adapter supports CeFi limit buy-backs only; no market fallback')
        result = self.call(buyer, 'POST', '/v1/gateway/quotes', {
            'base_asset': asset['symbol'], 'quote_asset': stable['symbol'],
            'qty': str(quantity), 'qty_unit': 'base', 'side': 'buy'})
        if 'fee' not in result or 'price' not in result:
            raise ValueError('Limit preview missing price or fee')
        return result

    def create_limit(self, buyer, asset, quantity, price):
        # Can submit immediately: caller must persist state and check approval first.
        if dry_run():
            raise RuntimeError('DRY_RUN prevents limit order creation')
        return self.call(buyer, 'POST', '/v1/gateway/orders', {
            'asset_id': asset['id'], 'qty': str(quantity), 'qty_unit': 'base',
            'side': 'buy', 'type': 'limit', 'price': str(price), 'venue': 'cefi'})

    def read_order(self, buyer, ident):
        return public(self.call(buyer, 'GET', f'/v1/gateway/orders/{ident}'))

    def prepare_transfer(self, buyer, asset_id, quantity, recipient):
        return self.call(buyer, 'POST', '/v1/gateway/transfers',
                         {'asset_id': asset_id, 'qty': str(quantity),
                          'qty_unit': 'base', 'to': recipient})

    def preview_transfer(self, buyer, asset_id, quantity, recipient):
        # Unsigned preparation verifies vendor minima and fees before asking a
        # human to approve an otherwise impossible pay-in-kind payment.
        return public(self.prepare_transfer(buyer, asset_id, quantity, recipient))

    def submit(self, buyer, kind, prepared, guard):
        if dry_run():
            raise RuntimeError('DRY_RUN prevents signing and submission')
        guard()
        payloads = prepared.get('payloads', [])
        if not payloads:
            raise ValueError('Expected unsigned signing payloads')
        for p in payloads:
            if hashlib.sha256(p['payload'].encode()).hexdigest() != p['digest']:
                raise ValueError('Signing payload digest mismatch')
        # Select signer by buyer, never by whichever key file happens to exist.
        path = self.signer_files.get(buyer)
        if not path:
            raise ValueError('No signer explicitly configured for buyer')
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        from truemarkets.auth import turnkey_stamp
        bundle = json.loads(Path(path).read_text())
        key = ec.derive_private_key(int(bundle['signer_private_key'], 16), ec.SECP256R1())
        pub = key.public_key().public_bytes(serialization.Encoding.X962,
                                            serialization.PublicFormat.CompressedPoint).hex()
        if pub != bundle['signer_public_key'] or bundle['external_ref_id'] != buyer:
            raise ValueError('Signer does not match buyer')
        signatures = []
        for p in payloads:
            guard()  # Re-read human approval immediately before every signature.
            if dry_run():
                raise RuntimeError('DRY_RUN prevents signing')
            signatures.append(turnkey_stamp(key, p['payload'].encode()))
        guard()
        if dry_run():
            raise RuntimeError('DRY_RUN prevents submission')
        ident = prepared['order_id'] if kind == 'orders' else prepared['id']
        return self.call(buyer, 'POST', f'/v1/gateway/{kind}/{ident}/execute',
                         {'signatures': signatures, 'auth_type': 'api_key'})

    def confirm(self, buyer, kind, ident, timeout=45):
        deadline = time.monotonic() + timeout
        while True:
            result = self.call(buyer, 'GET', f'/v1/gateway/{kind}/{ident}')
            if result['status'] in {'complete', 'completed', 'failed', 'canceled'}:
                return public(result)
            if time.monotonic() >= deadline:
                raise TimeoutError('Submitted operation needs reconciliation; do not resubmit')
            time.sleep(2)

    def create_wallet(self, name):
        """Gateway creates a user plus both wallets. No funds move."""
        if dry_run():
            return {'dry_run': True, 'external_ref_id': name, 'wallets': [],
                    'action': 'create Gateway user and wallets with a new local signer'}
        # Generate once, persist before API call; retries must use the same key.
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        root = Path('.runway/signers')
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not name or len(name) > 64 or any(not (c.isascii() and (c.isalnum() or c in '_-')) for c in name):
            raise ValueError('Invalid external_ref_id')
        path = root / (name + '.json')
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            bundle = json.loads(path.read_text())
        else:
            key = ec.generate_private_key(ec.SECP256R1())
            bundle = {'external_ref_id': name,
                      'signer_private_key': key.private_numbers().private_value.to_bytes(32, 'big').hex(),
                      'signer_public_key': key.public_key().public_bytes(
                          serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint).hex()}
            with os.fdopen(fd, 'w') as f:
                json.dump(bundle, f)
        org = self.client.organization_id()
        result = self.client.request('POST', f'/v1/account/organizations/{org}/users', body={
            'external_ref_id': name, 'signer_public_key': bundle['signer_public_key']})
        self.signer_files[name] = str(path)
        self.users[name] = result
        return result
