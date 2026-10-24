"""Conservative weighted-average cost basis; unknown deposits never become gains."""
from decimal import Decimal


def dec(value):
    n = Decimal(str(value))
    if not n.is_finite():
        raise ValueError('A finite decimal is required')
    return n


def remaining_basis(history, asset_id, balance):
    """Normalized confirmed fills only, chronologically ordered.

    Each row: asset_id, action buy/sell, quantity, value_usd, fee_usd,
    timestamp. Adapter must paginate complete API history first. Missing basis,
    deposits, or unmatched balances fail closed rather than infer free principal.
    """
    quantity = Decimal(0)
    basis = Decimal(0)
    for row in sorted(history, key=lambda r: r['timestamp']):
        if row['asset_id'] != asset_id:
            continue
        qty = dec(row['quantity'])
        if qty <= 0:
            raise ValueError('Invalid history quantity')
        if row['action'] == 'buy':
            quantity += qty
            basis += dec(row['value_usd']) + dec(row['fee_usd'])
        elif row['action'] == 'sell' and quantity >= qty:
            basis *= (quantity - qty) / quantity
            quantity -= qty
        else:
            raise ValueError('Unknown acquisition cost or incomplete history')
    if abs(quantity - dec(balance)) > Decimal('0.000000001'):
        raise ValueError('History does not reconcile to holdings; principal protected')
    return basis


def spendable_gains(history, asset_id, balance, price):
    return max(Decimal(0), dec(balance) * dec(price) -
               remaining_basis(history, asset_id, balance))


def top_up_budget(total_usd, current_value_usd, target_weight, stable_available_usd):
    weight = dec(target_weight)
    if not 0 <= weight <= 1:
        raise ValueError('Target allocation must be between 0 and 1')
    return max(Decimal(0), min(dec(stable_available_usd),
                              dec(total_usd) * weight - dec(current_value_usd)))
