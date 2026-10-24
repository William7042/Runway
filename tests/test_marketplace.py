from copy import deepcopy
import pytest
from test_product_integration import integrated


def register(client, simulated=False):
    response=client.post('/specialists',json={'name':'Reviewer','capability':'Review agent payment flows',
        'price_usd':1,'accepts':['USDC'],'payout_user':'test2','simulated':simulated})
    assert response.status_code==201
    return response.json()


def job(client, seller, key='request-1234'):
    r=client.post('/specialist-jobs',json={'specialist_id':seller['id'],'buyer':'test',
        'request':'Review my payment flow','idempotency_key':key})
    assert r.status_code==201
    return r.json()


def bind(client, j, **patch):
    p={'buyer':'test','seller':'test2','amount_usd':1,'purpose':'Purchase review',
       'path':[{'type':'transfer','asset':'USDC','amount':1}], 'expected_cost':0,
       'alternatives':[],'drift':None,'flags':[],'source':'user:specialist-job:'+j['id']}
    p.update(patch)
    p=client.post('/proposals',json=p).json()
    r=client.post(f'/specialist-jobs/{j["id"]}/payment',json={'proposal_id':p['id']})
    return p,r


def pay(client,p,actual='1',simulated=False):
    assert client.post(f'/proposals/{p["id"]}/decision',json={'decision':'approve','reason':'isolated test human'}).status_code==200
    return client.post(f'/proposals/{p["id"]}/receipt',json={'status':'executed','tx_hash':None if simulated else 'test-chain-hash',
        'quote':{'simulated':simulated},'fill':{'execution_quality':{'expected_received':'1','actual_received':actual,'shortfall':str(max(0,1-float(actual)))}}})


def test_register_persists_and_never_exposes_owner_secret(integrated):
    _,_,c=integrated
    seller=register(c)
    public=c.get('/specialists').json()
    assert any(s['id']==seller['id'] for s in public)
    assert seller['owner_token'] not in str(public)
    assert 'owner_token_hash' not in str(public)
    assert c.get('/specialists/'+seller['id']).json()['name']=='Reviewer'
    assert c.patch('/specialists/'+seller['id'],json={'owner_token':'wrong','price_usd':2}).status_code==403
    assert c.patch('/specialists/'+seller['id'],json={'owner_token':seller['owner_token'],'price_usd':2}).status_code==200


def test_job_retry_price_freeze_and_idempotency(integrated):
    _,_,c=integrated;s=register(c);j=job(c,s)
    assert job(c,s)['id']==j['id']
    c.patch('/specialists/'+s['id'],json={'owner_token':s['owner_token'],'price_usd':2})
    assert c.get('/specialist-jobs/'+j['id']).json()['price_usd']==1
    assert job(c,s,key='request-5678')['price_usd']==2
    r=c.post('/specialist-jobs',json={'specialist_id':s['id'],'buyer':'test','request':'A changed request','idempotency_key':'request-1234'})
    assert r.status_code==409


@pytest.mark.parametrize('patch',[{'seller':'attacker'},{'buyer':'another'},{'amount_usd':2},
    {'source':'unrelated'},{'path':[{'type':'transfer','asset':'ETH','amount':1}]}])
def test_invoice_cannot_be_rebound(integrated,patch):
    _,_,c=integrated;s=register(c);j=job(c,s)
    _,r=bind(c,j,**patch)
    assert r.status_code==409


def test_unpaid_and_approved_work_stays_locked(integrated):
    _,_,c=integrated;s=register(c);j=job(c,s);p,r=bind(c,j)
    assert r.status_code==200
    args={'owner_token':s['owner_token'],'result':'Reviewed'}
    assert c.post(f'/specialist-jobs/{j["id"]}/result',json=args).status_code==409
    c.post(f'/proposals/{p["id"]}/decision',json={'decision':'approve'})
    assert c.post(f'/specialists/{s["id"]}/jobs',json={'owner_token':s['owner_token']}).json()==[]
    assert c.post(f'/specialist-jobs/{j["id"]}/result',json=args).status_code==409


@pytest.mark.parametrize('short',[False,True])
def test_paid_vendor_delivery_is_bound_and_idempotent(integrated,short):
    _,_,c=integrated;s=register(c);j=job(c,s);p,_=bind(c,j)
    assert pay(c,p,actual='0.5' if short else '1').status_code==200
    args={'owner_token':s['owner_token'],'result':'Three concrete findings'}
    r=c.post(f'/specialist-jobs/{j["id"]}/result',json=args)
    if short:
        assert r.status_code==409;return
    assert r.status_code==200 and r.json()['status']=='complete'
    assert c.post(f'/specialist-jobs/{j["id"]}/result',json=args).status_code==200
    assert c.post(f'/specialist-jobs/{j["id"]}/result',json={**args,'result':'Different'}).status_code==409
    assert c.post(f'/specialist-jobs/{j["id"]}/result',json={**args,'owner_token':'other'}).status_code==403
    assert c.get('/specialist-jobs/'+j['id']).json()['result']==args['result']
    assert len(c.get('/proposals').json())==4 # three seeds + one invoice


def test_simulated_receipt_cannot_unlock_live_job(integrated):
    _,_,c=integrated;s=register(c);j=job(c,s);p,_=bind(c,j)
    pay(c,p,simulated=True)
    assert c.get('/specialist-jobs/'+j['id']).json()['status']=='awaiting_payment'


def test_bounty_claim_submit_and_duplicate_claim(integrated):
    _,_,c=integrated
    b=c.post('/bounties',json={'title':'Demo review','price_usd':1}).json()
    assert c.post('/bounties/'+b['id']+'/claim',json={'claimant':'test2'}).status_code==200
    assert c.post('/bounties/'+b['id']+'/claim',json={'claimant':'other'}).status_code==409
    assert c.post('/bounties/'+b['id']+'/submit',json={'submission':'Review completed'}).status_code==200
    saved=next(x for x in c.get('/bounties').json() if x['id']==b['id'])
    assert saved['status']=='submitted' and saved['claimant']=='test2'
    assert saved['escrow_funded'] is False


def test_registration_rejects_unsupported_tokens_and_credentials_in_urls(integrated):
    _,_,c=integrated
    body={'name':'Reviewer','capability':'Review payment flow','price_usd':1,'accepts':['OTHER'],'payout_user':'test2'}
    assert c.post('/specialists',json=body).status_code==422
    assert c.post('/specialists',json={**body,'accepts':['USDC'],'endpoint':'https://secret:pass@example.com'}).status_code==422
