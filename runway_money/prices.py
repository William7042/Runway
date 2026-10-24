"""Injectable reference prices. Override with a UI slider for simulation only."""
from decimal import Decimal
import time
import httpx


class ReferencePrices:
    def __init__(self, overrides=None, client=None):
        self.overrides = overrides or {}
        self.client = client or httpx.Client(timeout=15)
        self.cache = {}

    def __call__(self, asset):
        symbol = asset['symbol']
        if symbol in self.overrides:
            return Decimal(str(self.overrides[symbol]))
        if asset.get('stable'):
            # Explicit demo assumption, surfaced in proposal flags.
            return Decimal(1)
        key = asset['id']
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < 30:
            return cached[1]
        if asset.get('reference_symbol'):
            r = self.client.get('https://query1.finance.yahoo.com/v8/finance/chart/' +
                                asset['reference_symbol'], params={'interval': '1d', 'range': '5d'})
            r.raise_for_status()
            meta = r.json()['chart']['result'][0]['meta']
            if time.time() - meta['regularMarketTime'] > 4 * 24 * 3600:
                raise ValueError('Stock reference price is stale')
            value = Decimal(str(meta['regularMarketPrice']))
        else:
            r = self.client.get('https://api.coingecko.com/api/v3/simple/price',
                                params={'ids': asset['slug'], 'vs_currencies': 'usd',
                                        'include_last_updated_at': 'true'})
            r.raise_for_status()
            data = r.json()
            price_id = asset['slug']
            if price_id not in data:
                # Catalog slugs are not necessarily CoinGecko IDs (e.g. a
                # ticker-like slug). Resolve by exact name + symbol, fail on ambiguity.
                search = self.client.get('https://api.coingecko.com/api/v3/search',
                                         params={'query':asset['name']})
                search.raise_for_status()
                matches = [c['id'] for c in search.json()['coins']
                           if c['symbol'].casefold() == symbol.casefold()
                           and c['name'].casefold() == asset['name'].casefold()]
                if len(matches) != 1:
                    raise ValueError('Independent price asset identity is ambiguous')
                price_id = matches[0]
                r = self.client.get('https://api.coingecko.com/api/v3/simple/price',
                    params={'ids':price_id,'vs_currencies':'usd','include_last_updated_at':'true'})
                r.raise_for_status()
                data = r.json()
            item = data[price_id]
            if time.time() - item['last_updated_at'] > 300:
                raise ValueError('Crypto reference price is stale')
            value = Decimal(str(item['usd']))
        if not value.is_finite() or value <= 0:
            raise ValueError('Reference price unavailable')
        self.cache[key] = (time.monotonic(), value)
        return value


def drift_bps(on_chain_price, reference_price):
    chain, reference = Decimal(str(on_chain_price)), Decimal(str(reference_price))
    if not reference.is_finite() or reference <= 0 or not chain.is_finite() or chain <= 0:
        raise ValueError('Valid positive prices required')
    return abs(chain / reference - 1) * 10000
