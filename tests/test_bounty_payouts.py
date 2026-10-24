import pytest
from test_product_integration import integrated
from runway_money.bounties import execute_payout
from runway_money.queue import ApprovalError


def submitted(client, *, worker='seller', asset='USDCOIN'):
    response=client.post('/bounties',json={'title':'Review this flow','description':'Return three findings',
        'price_usd':1,'poster':'buyer','asset':asset})
    assert response.status_code==201
    bounty=response.json()
    assert bounty['payment_mode']=='direct' and bounty['funding_proposal_id'] is None
    client.post(f'/bounties/{bounty["id"]}/claim',json={'claimant':worker}).raise_for_status()
    client.post(f'/bounties/{bounty["id"]}/submit',json={'submission':'Three findings delivered'}).raise_for_status()
    return bounty


def get_bounty(client,ident):
    return next(b for b in client.get('/bounties').json() if b['id']==ident)


def test_real_router_bounty_requires_separate_human_approval_and_pays_once(integrated,monkeypatch):
    router,backend,c=integrated
    monkeypatch.setattr('runway_money.bounties.get_router',lambda:router)
    b=submitted(c)
    assert len(c.get('/proposals').json())==3 # no funding proposal
    response=c.post(f'/bounties/{b["id"]}/verify',json={'decision':'approve','reason':'Reviewed work'})
    assert response.status_code==200
    b=response.json();ident=b['settlement_proposal_id']
    p=c.get('/proposals/'+ident).json()
    assert p['status']=='pending' and p['buyer']=='buyer' and p['seller']=='seller'
    assert p['bounty_role']=='payout' and p['bounty_id']==b['id']
    with pytest.raises(ApprovalError): execute_payout(b,router)
    c.post('/proposals/'+ident+'/decision',json={'decision':'approve','reason':'Test human approves exact payout'}).raise_for_status()
    preview=execute_payout(b,router)
    assert preview['status']=='approved' and not preview['tx_hash']
    assert get_bounty(c,b['id'])['status']=='submitted'
    assert backend.submissions==[]
    monkeypatch.setenv('DRY_RUN','0')
    receipt=execute_payout(b,router)
    assert receipt['status']=='executed' and receipt['tx_hash']=='real-chain-hash'
    assert get_bounty(c,b['id'])['status']=='paid'
    assert execute_payout(b,router)==receipt
    assert backend.submissions==['transfers']
    assert c.post(f'/bounties/{b["id"]}/verify',json={'decision':'approve'}).status_code==409


def test_rejecting_work_sends_no_money_or_refund(integrated):
    _,backend,c=integrated;b=submitted(c)
    r=c.post(f'/bounties/{b["id"]}/verify',json={'decision':'reject','reason':'Incomplete'})
    assert r.status_code==200 and r.json()['status']=='rejected'
    assert not r.json().get('settlement_proposal_id')
    assert len(c.get('/proposals').json())==3 and not backend.submissions


@pytest.mark.parametrize('worker,asset',[('unregistered','USDCOIN'),('seller','OTHER')])
def test_unavailable_worker_or_asset_cannot_create_a_fake_payout(integrated,monkeypatch,worker,asset):
    router,backend,c=integrated;monkeypatch.setattr('runway_money.bounties.get_router',lambda:router)
    b=submitted(c,worker=worker,asset=asset)
    r=c.post(f'/bounties/{b["id"]}/verify',json={'decision':'approve'})
    assert r.status_code==409
    assert len(c.get('/proposals').json())==3 and not backend.submissions


def test_stub_receipt_does_not_mark_direct_bounty_paid(integrated,monkeypatch):
    router,_,c=integrated;monkeypatch.setattr('runway_money.bounties.get_router',lambda:router)
    b=submitted(c)
    b=c.post(f'/bounties/{b["id"]}/verify',json={'decision':'approve'}).json();p=b['settlement_proposal_id']
    c.post('/proposals/'+p+'/decision',json={'decision':'approve'})
    c.post('/proposals/'+p+'/receipt',json={'status':'executed','tx_hash':'STUB-fake','quote':{'simulated':True},'fill':{'simulated':True}})
    saved=get_bounty(c,b['id'])
    assert saved['status']=='submitted' and saved['payout_issue']
