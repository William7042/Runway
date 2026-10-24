"""Real direct bounty payouts. No escrow, no payment before human approval."""
import asyncio
from copy import copy
import logging
from .router import build_router
from .state import fingerprint

logger=logging.getLogger(__name__)
_router=None


def get_router():
    global _router
    if _router is None:
        _router=build_router()
    return _router


def draft_payout(bounty, router=None):
    router=router or get_router()
    seller=bounty['claimant']
    if seller not in router.sellers:
        raise ValueError('Worker must be a configured True Markets payout recipient')
    policy=router.sellers[seller]
    catalog={a['id']:a for a in router.backend.assets()}
    selected=[ident for ident in policy['accepted_asset_ids']
              if ident in catalog and catalog[ident]['symbol']==bounty['asset']]
    if not selected:
        raise ValueError('Worker does not accept the bounty reward token')
    scoped=copy(router)
    scoped.sellers={**router.sellers,seller:{**policy,'accepted_asset_ids':selected}}
    proposal=scoped.draft_payment(bounty['poster'],seller,bounty['price_usd'],
        'Pay for human-reviewed bounty work: '+bounty['title'], 'user:bounty:'+bounty['id'])
    proposal.update(bounty_id=bounty['id'],bounty_role='payout')
    proposal['flags'].append('Direct bounty payout: funds stayed with the poster until this payment; no escrow or guaranteed reservation.')
    plan=router.state.read(proposal['id'])
    plan.update(proposal=proposal,fingerprint=fingerprint(proposal))
    router.state.write(proposal['id'],plan)
    return proposal


def execute_payout(bounty, router=None):
    router=router or get_router()
    proposal=router.queue.get(bounty['settlement_proposal_id'])
    if (not proposal or proposal.get('bounty_id')!=bounty['id'] or proposal.get('bounty_role')!='payout'
            or proposal['buyer']!=bounty['poster'] or proposal['seller']!=bounty['claimant']):
        raise ValueError('Payment is not bound to this bounty and worker')
    # The real router checks approval, immutable invoice, fees, preflight, and DRY_RUN.
    return router.execute(proposal['id'])


async def watch(approved_bounties, *, interval=2):
    """Execute only direct bounty plans already approved by a human. Never approve."""
    while True:
        try:
            for bounty in approved_bounties():
                try:
                    await asyncio.to_thread(execute_payout,bounty)
                except Exception as exc:
                    logger.warning('Bounty payout unavailable for %s (%s)',bounty['id'],type(exc).__name__)
        except Exception as exc:
            logger.warning('Bounty payout watcher unavailable (%s)',type(exc).__name__)
        await asyncio.sleep(interval)
