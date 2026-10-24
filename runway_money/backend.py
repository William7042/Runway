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
        self._checked_digests = set()

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

    def prepare_swap(self, buyer, source, target, quantity):
        """Stable conversion uses DeFi quote/trade; token buys use Gateway orders."""
        if source['chain'] != 'solana' or target['chain'] != 'solana':
            raise ValueError('Guarded standalone swap currently supports Solana only')
        if not source.get('stable'):
            raise ValueError('Standalone demo swap must spend a stablecoin')
        if target.get('stable'):
            result = self.call(buyer, 'POST', '/v1/defi/core/quote', {
                'chain': 'solana', 'base_asset': source['address'], 'quote_asset': target['address'],
                'order_side': 'sell', 'qty': str(quantity), 'qty_unit': 'base', 'order_type': 'market'})
            kind = 'trades'
            if result.get('base_asset') != source['address'] or result.get('quote_asset') != target['address']:
                raise ValueError('Stable conversion changed its asset pair')
        else:
            if not target.get('tradeable') or target.get('type', 'spot') != 'spot':
                raise ValueError('Swap target is not a tradable spot asset')
            result = self.call(buyer, 'POST', '/v1/gateway/orders', {
                'asset_id': target['id'], 'qty': str(quantity), 'qty_unit': 'quote',
                'side': 'buy', 'type': 'market', 'venue': 'defi'})
            kind = 'orders'
            q = result.get('quote', {})
            if q.get('quote_asset') != source['address'] or q.get('base_asset') != target['address']:
                raise ValueError('Gateway order changed its settlement pair')
        q = result.get('quote', result)
        if q.get('issues') or q.get('bridge_state') or len(result.get('payloads', [])) != 1:
            raise ValueError('Swap has quote issues or requires an unverified bridge')
        return kind, result

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
        # Awaiting-signature fee/received fields are not reliable quote fields.
        # Inspect the actual unsigned transaction's wallet economics instead.
        from .preflight import SolanaPreflight, token_deltas
        prepared = self.prepare_transfer(buyer, asset_id, quantity, recipient)
        asset = next(a for a in self.assets() if a['id'] == asset_id)
        if asset['chain'] != 'solana' or asset['symbol'] == 'SOL':
            raise ValueError('Fee-aware transfer preview currently supports Solana tokens only')
        wallet = next(w['address'] for w in self.user(buyer)['wallets'] if w['chain_family'] == 'solana')
        evidence = SolanaPreflight(os.getenv('RUNWAY_SOLANA_RPC', 'https://api.mainnet-beta.solana.com')).inspect(prepared, wallet)
        changes = evidence['token_deltas']
        sent = -changes.get(asset['address'], Decimal(0))
        received = token_deltas(evidence['_simulation'], recipient).get(asset['address'], Decimal(0))
        if (sent != dec(quantity) or not 0 <= received <= sent or evidence['native_delta'] < 0 or
            any(v < 0 and mint != asset['address'] for mint,v in changes.items())):
            raise ValueError('Transfer has unexpected wallet debits or recipient amounts')
        return {**public(prepared), 'api_reported_fee':prepared['fee'],
                'api_reported_received':prepared['received'],
                'sent':str(sent), 'received':str(received), 'fee':str(sent-received),
                'fee_source':'unsigned_solana_simulation'}

    def submit(self, buyer, kind, prepared, guard):
        if dry_run():
            raise RuntimeError('DRY_RUN prevents signing and submission')
        guard()
        payloads = prepared.get('payloads', [])
        if not payloads:
            raise ValueError('Expected unsigned signing payloads')
        if any(p['digest'] not in self._checked_digests for p in payloads):
            raise ValueError('Unsigned transaction economics have not passed preflight')
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
        if kind == 'trades':
            return self.call(buyer, 'POST', '/v1/defi/core/trade', {
                'quote_id': prepared['quote_id'], 'signatures': signatures, 'auth_type': 'api_key'})
        ident = prepared['order_id'] if kind == 'orders' else prepared['id']
        return self.call(buyer, 'POST', f'/v1/gateway/{kind}/{ident}/execute',
                         {'signatures': signatures, 'auth_type': 'api_key'})

    def preflight(self, buyer, kind, prepared, plan):
        from .preflight import SolanaPreflight
        if plan['source_asset']['chain'] != 'solana':
            raise ValueError('Live preflight currently supports Solana only')
        wallet = next(w['address'] for w in self.user(buyer)['wallets'] if w['chain_family'] == 'solana')
        result = SolanaPreflight(os.getenv('RUNWAY_SOLANA_RPC', 'https://api.mainnet-beta.solana.com')).verify(
            prepared, wallet, input_asset=plan['source_asset'], output_asset=plan['target_asset'],
            max_input=plan['input_qty'], min_output=plan['pay_qty'],
            recipient=plan['recipient'] if kind == 'transfers' else None)
        self._checked_digests.add(result['digest'])
        return {k: v for k, v in result.items() if k != 'token_deltas'}

    def audit_swap(self, buyer, tx_hash, plan):
        import httpx
        from .preflight import token_deltas
        wallet = next(w['address'] for w in self.user(buyer)['wallets'] if w['chain_family'] == 'solana')
        response = httpx.post(os.getenv('RUNWAY_SOLANA_RPC', 'https://api.mainnet-beta.solana.com'),
            json={'jsonrpc':'2.0','id':1,'method':'getTransaction',
                  'params':[tx_hash,{'encoding':'jsonParsed','maxSupportedTransactionVersion':0}]}, timeout=20)
        response.raise_for_status()
        tx = response.json().get('result')
        if not tx or tx['meta']['err'] is not None:
            raise ValueError('Confirmed swap chain evidence unavailable')
        meta = tx['meta']
        deltas = token_deltas(meta, wallet)
        keys = tx['transaction']['message']['accountKeys']
        index = next(i for i,k in enumerate(keys) if (k['pubkey'] if isinstance(k,dict) else k) == wallet)
        native = (dec(meta['postBalances'][index]) - dec(meta['preBalances'][index])) / 10**9
        src, target = plan['source_asset'], plan['target_asset']
        spent = -deltas.get(src['address'], Decimal(0))
        received = deltas.get(target['address'], Decimal(0)) + (native if target['symbol'] == 'SOL' else 0)
        matched = (0 <= spent <= dec(plan['input_qty']) and received >= dec(plan['pay_qty']) and native >= 0
                   and not any(v < 0 and k != src['address'] for k,v in deltas.items()))
        return {'matched_approved_bounds': matched, 'actual_input':str(spent),
                'actual_output':str(received), 'network_fee_lamports':meta['fee']}

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
