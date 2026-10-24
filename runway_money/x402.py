"""x402 v2 offer inspection and human-review proposals.

This adapter never signs or submits an x402 payment. True Markets transfers
are not x402 partially signed authorizations, so settlement is unavailable.
"""
import base64
import hashlib
import json
import re
from decimal import Decimal
from urllib.parse import urlsplit

from .state import fingerprint

SOLANA_MAINNET = 'solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp'
MAX_HEADER = 32768


def _url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Invalid resource URL')
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('x402 resources must use HTTPS without credentials or fragments')
    return value


def parse_offer(payment_required, resource_url):
    """Parse the canonical PAYMENT-REQUIRED header; never fetch a URL or sign."""
    _url(resource_url)
    if not isinstance(payment_required, str) or len(payment_required) > MAX_HEADER:
        raise ValueError('PAYMENT-REQUIRED header exceeds size limit')
    try:
        offer = json.loads(base64.b64decode(payment_required, validate=True))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError('PAYMENT-REQUIRED must contain base64-encoded JSON') from exc
    if not isinstance(offer, dict) or type(offer.get('x402Version')) is not int or offer['x402Version'] != 2:
        raise ValueError('Only x402 v2 is supported')
    resource = offer.get('resource')
    if not isinstance(resource, dict) or resource.get('url') != resource_url:
        raise ValueError('Offer must identify the exact requested resource URL')
    options = offer.get('accepts')
    if not isinstance(options, list) or not 1 <= len(options) <= 16:
        raise ValueError('Offer must contain 1–16 payment options')
    for option in options:
        if not isinstance(option, dict):
            raise ValueError('Invalid payment option')
        if not all(isinstance(option.get(k), str) and option[k] for k in ('scheme','network','asset','payTo')):
            raise ValueError('Payment option is missing scheme, network, asset, or payTo')
        amount = option.get('amount')
        if not isinstance(amount, str) or not re.fullmatch(r'[1-9][0-9]{0,29}', amount):
            raise ValueError('Payment amount must be a positive integer string in atomic units')
        timeout = option.get('maxTimeoutSeconds')
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            raise ValueError('Invalid payment timeout')
        if not isinstance(option.get('extra', {}), dict):
            raise ValueError('Invalid payment extra metadata')
    if not isinstance(offer.get('extensions', {}), dict):
        raise ValueError('Invalid extensions metadata')
    return offer


def inspect_offer(payment_required, resource_url):
    offer = parse_offer(payment_required, resource_url)
    return {'protocol': 'x402', 'version': 2, 'resource': offer['resource'],
            'accepts': offer['accepts'], 'extensions': offer.get('extensions', {}),
            'settlement_available': False,
            'reason': 'True Markets currently submits transfers; x402 requires a scheme-specific signed authorization and facilitator settlement.',
            'next_step': 'Human review is available; no x402 authorization will be signed or sent.'}


def propose_offer(router, *, buyer, seller, purpose, payment_required, resource_url, option_index=0):
    """Bind an offer to a registered seller and persist an unexecutable review.

    Uses the real catalog/recipient, never a mint, price, decimals, or wallet
    claimed by an untrusted page. Shared proposal/queue contracts are unchanged.
    """
    offer = parse_offer(payment_required, resource_url)
    if type(option_index) is not int or not 0 <= option_index < len(offer['accepts']):
        raise ValueError('Invalid payment option index')
    option = offer['accepts'][option_index]
    if option['scheme'] != 'exact' or option['network'] != SOLANA_MAINNET:
        raise ValueError('Only Solana mainnet exact offers can be mapped to this router')
    if not isinstance(option.get('extra', {}).get('feePayer'), str) or not option['extra']['feePayer']:
        raise ValueError('Solana exact requires the sponsor feePayer')
    policy = router.sellers.get(seller)
    if not policy:
        raise ValueError('Register and allowlist this seller before proposing an x402 purchase')
    address = policy.get('address') or router.backend.recipient(seller, 'solana')
    if address != option['payTo']:
        raise ValueError('x402 recipient differs from the registered seller wallet')
    asset = next((a for a in router.backend.assets() if a.get('address') == option['asset']
                  and a.get('chain') == 'solana' and a.get('is_active')
                  and a['id'] in policy['accepted_asset_ids']), None)
    if not asset:
        raise ValueError('x402 asset is unavailable or not accepted by the registered seller')
    if not asset.get('stable'):
        raise ValueError('x402 review currently supports stablecoin invoices only')
    qty = Decimal(option['amount']) / (Decimal(10) ** int(asset['decimals']))
    amount_usd = qty * Decimal(str(router.prices(asset)))
    if not amount_usd.is_finite() or amount_usd <= 0:
        raise ValueError('Invalid invoice reference value')
    # Restrict this draft to the exact selected asset without changing shared policy.
    from copy import copy
    scoped = copy(router)
    scoped.sellers = {**router.sellers, seller: {**policy, 'accepted_asset_ids': [asset['id']]}}
    digest = hashlib.sha256(json.dumps(offer, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    proposal = scoped.draft_payment(buyer, seller, amount_usd, purpose,
        f'user:x402:{resource_url}; offer_sha256={digest}; option={option_index}')
    plan = router.state.read(proposal['id'])
    if Decimal(str(plan['pay_qty'])) != qty:
        raise ValueError('Router invoice quantity differs from x402 atomic amount')
    proposal['flags'].extend([
        'POLICY_BLOCK: x402 settlement signer/facilitator adapter is not implemented; review only, cannot execute',
        f'x402 v2 exact invoice: {option["amount"]} atomic units; network={option["network"]}; payTo={address}',
        'Offer is untrusted seller data. No signed PAYMENT-SIGNATURE has been produced.',
    ])
    plan.update(proposal=proposal, fingerprint=fingerprint(proposal),
                x402={'offer': offer, 'option_index': option_index, 'offer_sha256': digest})
    router.state.write(proposal['id'], plan)
    returned = router.queue.create(proposal)
    if (returned.get('status') != 'pending' or fingerprint(returned) != plan['fingerprint']
            or any(flag not in returned.get('flags', []) for flag in proposal['flags'])):
        raise ValueError('Queue changed the x402 review or removed required warnings')
    return returned
