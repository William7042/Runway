"""Canned NVDAc demo. Never imports the SDK, signs, or submits a transaction."""
from decimal import Decimal
from uuid import uuid4
from .queue import HTTPQueue
from .prices import drift_bps


class StubRouter:
    def __init__(self, queue=None, *, reference_price=100, on_chain_price=100,
                 max_drift_bps=200):
        self.queue = queue or HTTPQueue()
        self.reference_price = Decimal(str(reference_price))
        self.on_chain_price = Decimal(str(on_chain_price))
        self.max_drift_bps = Decimal(str(max_drift_bps))

    def propose_payment(self, buyer, seller, amount_usd, purpose, source):
        amount = Decimal(str(amount_usd))
        if not amount.is_finite() or amount <= 0:
            raise ValueError("amount_usd must be positive and finite")
        gap = drift_bps(self.on_chain_price, self.reference_price)
        p = dict(id=str(uuid4()), buyer=buyer, seller=seller, purpose=purpose,
                 amount_usd=float(amount), path=[
                     {"type": "swap", "asset": "NVDAc", "amount": str(amount / self.on_chain_price)},
                     {"type": "transfer", "asset": "USDC", "amount": str(amount)}],
                 expected_cost=0.001, alternatives=[],
                 drift={"on_chain_price": float(self.on_chain_price),
                        "reference_price": float(self.reference_price), "bps": float(gap)},
                 flags=["SIMULATED: canned NVDAc prices and holdings; no funds move"],
                 source=source, status="pending")
        if gap > self.max_drift_bps:
            p['alternatives'] = [{'path': p['path'], 'rejected_reason': 'Simulated NVDAc drift exceeds threshold'}]
            p['path'] = [{'type': 'transfer', 'asset': 'USDC', 'amount': str(amount)}]
            p['expected_cost'] = 0
            p['flags'].append('SIMULATED: pay stablecoin instead of selling NVDAc at excessive drift')
        return self.queue.create(p)

    def execute(self, proposal_id):
        p = self.queue.approved(proposal_id)
        receipt = dict(quote={"simulated": True, "path": p["path"]},
                       fill={"simulated": True, "amount_usd": p["amount_usd"]},
                       tx_hash=None, status="executed")
        self.queue.receipt(proposal_id, receipt)
        return receipt
