"""Buyer/seller tools. Human financial decisions stay in the dashboard."""
from . import queue_http as q


def install(mcp):
    @mcp.tool()
    def register_specialist(name: str, capability: str, price_usd: float,
                            payout_user: str, accepted_assets_csv: str = 'USDC',
                            endpoint: str = '', simulated: bool = False) -> dict:
        """List your specialist. payout_user is a registered True Markets user (e.g. test2).

        Returns a private owner_token once; keep it for listing updates and job delivery.
        Vendor runs its own worker and polls list_specialist_jobs. No model key is needed.
        Registration does not configure signing keys or verify a payment route.
        """
        return q._req('POST','/specialists',json={'name':name,'capability':capability,
            'price_usd':price_usd,'payout_user':payout_user,
            'accepts':[a.strip() for a in accepted_assets_csv.split(',') if a.strip()],
            'endpoint':endpoint,'simulated':simulated})

    @mcp.tool()
    def update_specialist(specialist_id: str, owner_token: str,
                          price_usd: float | None = None, capability: str | None = None,
                          active: bool | None = None) -> dict:
        """Update your listing; existing job invoices retain their original price."""
        return q._req('PATCH',f'/specialists/{specialist_id}',json={k:v for k,v in
            {'owner_token':owner_token,'price_usd':price_usd,'capability':capability,'active':active}.items() if v is not None})

    @mcp.tool()
    def request_specialist_job(specialist_id: str, buyer: str, request: str,
                                idempotency_key: str) -> dict:
        """Request work and enqueue its payment for HUMAN approval. Never executes.

        Reuse idempotency_key when retrying the same job. Live sellers require
        RUNWAY_MODE=live and a preconfigured money-layer recipient/asset policy.
        Simulated listings can use the stub. No agent model API key is required.
        """
        import os
        from copy import copy
        from runway_money import get_router
        from runway_money.state import State
        job=q._req('POST','/specialist-jobs',json={'specialist_id':specialist_id,
            'buyer':buyer,'request':request,'idempotency_key':idempotency_key})
        with State('.runway/job-payment-locks').lock(job['id']):
            job=q._req('GET',f'/specialist-jobs/{job["id"]}')
            if job.get('proposal_id'): return job
            source='user:specialist-job:'+job['id']
            # Recover an enqueue that succeeded before a transport interruption.
            for p in q.list_proposals():
                src=p.get('source');src=src.get('text') if isinstance(src,dict) else src
                if src==source:
                    return q._req('POST',f'/specialist-jobs/{job["id"]}/payment',json={'proposal_id':p['id']})
            live=os.getenv('RUNWAY_MODE','stub')=='live'
            if not live and not job['simulated']:
                return {**job,'payment_error':'Live seller requires RUNWAY_MODE=live; no simulated payment was created.'}
            router=get_router()
            if live:
                if job['seller'] not in router.sellers:
                    return {**job,'payment_error':'Seller payout user must be configured in the money-layer recipient allowlist.'}
                scoped=copy(router)
                original=router.sellers[job['seller']]
                assets={a['id']:a for a in router.backend.assets()}
                ids=[ident for ident in original['accepted_asset_ids']
                     if ident in assets and assets[ident]['symbol'] in job['accepts']]
                scoped.sellers={**router.sellers,job['seller']:{**original,'accepted_asset_ids':ids}}
                router=scoped
            elif 'USDC' not in job['accepts']:
                return {**job,'payment_error':'The simulated payment adapter requires USDC acceptance.'}
            p=router.propose_payment(buyer,job['seller'],job['price_usd'],
                f'Purchase specialist job {job["id"]}: {request[:500]}',source)
            return q._req('POST',f'/specialist-jobs/{job["id"]}/payment',json={'proposal_id':p['id']})

    @mcp.tool()
    def get_specialist_job(job_id: str) -> dict:
        """Buyer polls payment status or retrieves the completed specialist result."""
        return q._req('GET',f'/specialist-jobs/{job_id}')

    @mcp.tool()
    def execute_specialist_payment(job_id: str) -> dict:
        """Execute this job's exact payment ONLY after dashboard approval.

        DRY_RUN previews only; it never unlocks paid work. No approval tool is exposed.
        """
        from runway_money import get_router
        job=q._req('GET',f'/specialist-jobs/{job_id}')
        if not job.get('proposal_id'): return {'error':'Job has no payment proposal'}
        p=q.get_proposal(job['proposal_id'])
        if p['status']!='approved': return {'error':'Human dashboard approval required','status':p['status']}
        return get_router().execute(job['proposal_id'])

    @mcp.tool()
    def list_specialist_jobs(specialist_id: str, owner_token: str) -> str:
        """Seller polls confirmed paid jobs only. Approved-but-unpaid jobs stay locked."""
        import json
        return json.dumps(q._req('POST',f'/specialists/{specialist_id}/jobs',json={'owner_token':owner_token}))

    @mcp.tool()
    def submit_specialist_result(job_id: str, owner_token: str, result: str) -> dict:
        """Seller delivers work for its confirmed paid job. Same-result retries are idempotent."""
        return q._req('POST',f'/specialist-jobs/{job_id}/result',json={'owner_token':owner_token,'result':result})
