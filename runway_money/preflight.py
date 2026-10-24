"""Unsigned Solana simulation: verify wallet economics before any signature."""
import base64
import hashlib
import json
from decimal import Decimal
import httpx

ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'


def b58(raw):
    zeros = len(raw) - len(raw.lstrip(b'\0'))
    n, out = int.from_bytes(raw, 'big'), ''
    while n:
        n, digit = divmod(n, 58)
        out = ALPHABET[digit] + out
    return '1' * zeros + out


def static_keys(raw):
    """Read only the signed transaction header/static addresses (legacy or v0)."""
    pos = 0
    def short():
        nonlocal pos
        result = 0
        for shift in (0, 7, 14):
            byte = raw[pos]
            pos += 1
            result |= (byte & 127) << shift
            if byte < 128:
                return result
        raise ValueError('Malformed Solana short vector')
    count = short()
    if count > 16:
        raise ValueError('Unsupported signer count')
    pos += count * 64
    if raw[pos] & 128:
        if raw[pos] != 128:
            raise ValueError('Unsupported Solana message version')
        pos += 1
    signers = raw[pos]
    pos += 3
    count = short()
    keys = [b58(raw[pos + i * 32:pos + (i + 1) * 32]) for i in range(count)]
    if len(raw) < pos + count * 32 or signers > count:
        raise ValueError('Truncated Solana transaction')
    return keys, keys[:signers]


def token_deltas(value, owner):
    totals = {}
    for field, sign in [('preTokenBalances', -1), ('postTokenBalances', 1)]:
        if not isinstance(value.get(field), list):
            raise ValueError('RPC does not provide token balance evidence')
        for row in value[field]:
            if row.get('owner') == owner:
                token = row['uiTokenAmount']
                amount = Decimal(token['amount']) / Decimal(10) ** token['decimals']
                totals[row['mint']] = totals.get(row['mint'], Decimal(0)) + sign * amount
    return totals


class SolanaPreflight:
    def __init__(self, rpc_url='https://api.mainnet-beta.solana.com', client=None):
        self.rpc_url = rpc_url
        self.client = client or httpx.Client(timeout=20)

    def inspect(self, prepared, wallet):
        payloads = prepared.get('payloads', [])
        if len(payloads) != 1:
            raise ValueError('Multi-transaction bridge requires sequential economic verification; signing blocked')
        p = payloads[0]
        if hashlib.sha256(p['payload'].encode()).hexdigest() != p['digest']:
            raise ValueError('Payload digest mismatch')
        activity = json.loads(p['payload'])
        params = activity['parameters']
        if (activity['type'] != 'ACTIVITY_TYPE_SIGN_TRANSACTION_V2' or
            params['type'] != 'TRANSACTION_TYPE_SOLANA' or params['signWith'] != wallet):
            raise ValueError('Transaction activity does not match buyer Solana wallet')
        raw = bytes.fromhex(params['unsignedTransaction'])
        keys, signers = static_keys(raw)
        if wallet not in signers:
            raise ValueError('Buyer is not a required transaction signer')
        response = self.client.post(self.rpc_url, json={
            'jsonrpc': '2.0', 'id': 1, 'method': 'simulateTransaction',
            'params': [base64.b64encode(raw).decode(), {'encoding': 'base64',
                        'replaceRecentBlockhash': True, 'sigVerify': False}]})
        response.raise_for_status()
        body = response.json()
        if body.get('error') or not body.get('result'):
            raise ValueError('Unsigned simulation unavailable; signing blocked')
        result = body['result']['value']
        if result.get('err') is not None:
            raise ValueError('Unsigned transaction simulation failed; signing blocked')
        index = keys.index(wallet)
        native = (Decimal(result['postBalances'][index]) - Decimal(result['preBalances'][index])) / 10**9
        return {'digest': p['digest'], 'token_deltas': token_deltas(result, wallet),
                'native_delta': native, 'network_fee_lamports': result['fee'],
                '_simulation': result, '_keys': keys}

    def verify(self, prepared, wallet, *, input_asset, output_asset,
               max_input, min_output, recipient=None):
        result = self.inspect(prepared, wallet)
        deltas = result['token_deltas']
        # Native SOL uses the wallet lamport delta; wrapped SOL uses token balance.
        def delta(asset):
            if asset['symbol'] == 'SOL' and asset['chain'] == 'solana':
                return result['native_delta'] + deltas.get(asset['address'], Decimal(0))
            return deltas.get(asset['address'], Decimal(0))
        spent = -delta(input_asset)
        if spent < 0 or spent > Decimal(str(max_input)):
            raise ValueError('Simulated debit exceeds approved input')
        allowed = {input_asset['address'], output_asset['address']}
        if any(amount < 0 and mint not in allowed for mint, amount in deltas.items()):
            raise ValueError('Transaction spends an unapproved token')
        native_input = input_asset['symbol'] == 'SOL'
        if result['native_delta'] < 0 and not native_input:
            raise ValueError('Transaction also debits buyer SOL')
        if recipient is None:
            if delta(output_asset) < Decimal(str(min_output)):
                raise ValueError('Simulated output is below the human-approved minimum')
        else:
            received = token_deltas(result['_simulation'], recipient).get(output_asset['address'], Decimal(0))
            if output_asset['symbol'] == 'SOL' and output_asset['chain'] == 'solana':
                idx = result['_keys'].index(recipient)
                sim = result['_simulation']
                received += (Decimal(sim['postBalances'][idx]) - Decimal(sim['preBalances'][idx])) / 10**9
            if received < Decimal(str(min_output)):
                raise ValueError('Simulated recipient receives less than approved; hidden fee or wrong recipient')
        result.pop('_simulation')
        result.pop('_keys')
        return result
