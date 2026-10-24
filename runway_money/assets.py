"""Runway's supported commerce assets; identities/routes come from the API."""
COMMERCE_SYMBOLS = frozenset({'USDC', 'PYUSD', 'SOL', 'BTC', 'ETH'})


def allowed(asset, symbols=COMMERCE_SYMBOLS):
    return asset.get('symbol', '').upper() in symbols
