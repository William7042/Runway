import asyncio
import sys
import pytest
from test_product_integration import integrated
from runway_money import specialists
from runway_money.queue import ApprovalError


def invoice(c, router):
    # The fake backend's stablecoin is named USDCOIN; only this isolated
    # fixture adjusts the invoice symbol after registering a supported token.
    seller=c.post('/specialists',json={'name':'Reviewer','capability':'Review payment safety',
        'price_usd':1,'accepts':['USDC'],'payout_user':'seller','simulated':False})
    seller.raise_for_status()
    j=c.post('/specialist-jobs',json={'specialist_id':seller.json()['id'],'buyer':'buyer',
        'request':'Review payment safety','idempotency_key':'approved-invoice-test'}).json()
    module=sys.modules['test_product_queue']
    with module.Store() as s:
        next(x for x in s['specialist_jobs'] if x['id']==j['id'])['accepts']=['USDCOIN']
    j['accepts']=['USDCOIN']
    p=router.propose_payment('buyer','seller',1,'Review payment safety','user:specialist-job:'+j['id'])
    c.post('/specialist-jobs/'+j['id']+'/payment',json={'proposal_id':p['id']}).raise_for_status()
    j['proposal_id']=p['id']
    return j,p


def test_worker_pays_only_approved_invoice_once_and_respects_dry_run(integrated,monkeypatch):
    router,backend,c=integrated;j,p=invoice(c,router)
    with pytest.raises(ApprovalError):specialists.execute_payment(j,router)
    assert sys.modules['test_product_queue']._approved_specialist_jobs()==[]
    c.post('/proposals/'+p['id']+'/decision',json={'decision':'approve'}).raise_for_status()
    assert specialists.execute_payment(j,router)['status']=='approved'
    assert backend.submissions==[]
    monkeypatch.setenv('DRY_RUN','0')
    monkeypatch.setattr(specialists,'get_router',lambda:router)
    module=sys.modules['test_product_queue']
    async def run():
        task=asyncio.create_task(specialists.watch(module._approved_specialist_jobs,module._specialist_execution_issue,interval=.01))
        try:
            for _ in range(200):
                if c.get('/proposals/'+p['id']).json()['status']=='executed':break
                await asyncio.sleep(.01)
            assert c.get('/proposals/'+p['id']).json()['status']=='executed'
        finally:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
    asyncio.run(run())
    assert backend.submissions==['transfers']
    assert specialists.execute_payment(j,router)['status']=='executed'
    assert backend.submissions==['transfers']


def test_worker_rejects_changed_recipient_and_reports_expired_order(integrated,monkeypatch):
    router,backend,c=integrated;j,p=invoice(c,router)
    c.post('/proposals/'+p['id']+'/decision',json={'decision':'approve'})
    with pytest.raises(ValueError):specialists.execute_payment({**j,'seller':'other'},router)
    plan=router.state.read(p['id']);plan['created_at']-=600;router.state.write(p['id'],plan)
    monkeypatch.setenv('DRY_RUN','0');monkeypatch.setattr(specialists,'get_router',lambda:router)
    module=sys.modules['test_product_queue']
    async def run():
        task=asyncio.create_task(specialists.watch(module._approved_specialist_jobs,module._specialist_execution_issue,interval=.01))
        try:
            for _ in range(200):
                if c.get('/proposals/'+p['id']).json().get('execution_error'):break
                await asyncio.sleep(.01)
            assert c.get('/proposals/'+p['id']).json().get('execution_error')
            assert module._approved_specialist_jobs()==[]
        finally:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
    asyncio.run(run())
    assert backend.submissions==[]
