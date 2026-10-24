"""Execute specialist invoices after human approval; never approve an order."""
import asyncio
from decimal import Decimal
import logging
from .router import build_router

logger = logging.getLogger(__name__)
_router = None


def get_router():
    global _router
    if _router is None:
        _router = build_router()
    return _router


def execute_payment(job, router=None):
    router = router or get_router()
    proposal = router.queue.get(job['proposal_id'])
    source = proposal.get('source')
    source = source.get('text') if isinstance(source, dict) else source
    transfers = [step for step in proposal.get('path', []) if step['type'] == 'transfer']
    if (proposal['buyer'] != job['buyer'] or proposal['seller'] != job['seller']
            or Decimal(str(proposal['amount_usd'])) != Decimal(str(job['price_usd']))
            or source != 'user:specialist-job:' + job['id']
            or len(transfers) != 1 or transfers[0]['asset'] not in job['accepts']
            or job.get('simulated')):
        raise ValueError('Payment does not match the live specialist invoice')
    # Durable plan lock, human approval, fingerprint, DRY_RUN, expiry, fee and
    # transaction checks all remain enforced by the money router.
    return router.execute(proposal['id'])


async def watch(approved_jobs, report_issue, *, interval=0.5):
    """Resume approved invoices after restart; never blindly retry an uncertain send."""
    attempted = set()
    while True:
        try:
            for job in approved_jobs():
                ident = job['proposal_id']
                if ident in attempted:
                    continue
                attempted.add(ident)
                try:
                    await asyncio.to_thread(execute_payment, job)
                except Exception as exc:
                    logger.warning('Specialist payment stopped for %s (%s)', ident, type(exc).__name__)
                    report_issue(ident, 'Payment stopped before a confirmed receipt. The quote may have expired or a safety check failed. Inspect the saved plan before retrying; do not create a duplicate payment.')
        except Exception as exc:
            logger.warning('Specialist payment watcher unavailable (%s)', type(exc).__name__)
        await asyncio.sleep(interval)
