"""Person B model adapter; never signs or executes during agent planning."""
from . import get_router


def draft_payment(buyer, seller, amount_usd, purpose, source):
    from agent.models import Proposal
    router = get_router()
    if not hasattr(router, 'draft_payment'):
        raise ValueError('Live agent adapter requires RUNWAY_MODE=live')
    data = router.draft_payment(buyer, seller, amount_usd, purpose, source)
    if data['drift'] is not None:
        # Person B models use percent, whereas the core price guard uses bps.
        data['drift'] = {'on_chain_price': data['drift']['on_chain_price'],
                         'reference_price': data['drift']['reference_price'],
                         'gap_pct': data['drift']['bps'] / 100}
        # Persist the exact model shape the human will see.
        from .state import fingerprint
        plan = router.state.read(data['id'])
        plan['proposal'], plan['fingerprint'] = data, fingerprint(data)
        router.state.write(data['id'], plan)
    return Proposal.model_validate(data)


def transfer_fee_usd(proposal_id):
    """Read the deterministic router plan, never infer fees from model-written text."""
    return float(get_router().state.read(proposal_id)['transfer_fee_usd'])
