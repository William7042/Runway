import base64
from copy import deepcopy
import json
import pytest
from runway_money.x402 import SOLANA_MAINNET, parse_offer, inspect_offer, propose_offer
from runway_money.queue import ApprovalError
from test_money import setup

URL = 'https://specialist.example/jobs/review'


def offer():
    return {'x402Version': 2, 'resource': {'url': URL}, 'accepts': [{
        'scheme':'exact', 'network': SOLANA_MAINNET, 'amount':'1000000',
        'asset':'usd-mint', 'payTo':'registered-recipient', 'maxTimeoutSeconds':60,
        'extra': {'feePayer':'sponsor-address'}}], 'extensions': {'example': {'info': {'job':'123'}}}}


def header(value):
    return base64.b64encode(json.dumps(value).encode()).decode()


def test_reads_real_v2_header_without_claiming_settlement():
    result = inspect_offer(header(offer()), URL)
    assert result['version'] == 2
    assert result['settlement_available'] is False
    assert result['accepts'][0]['amount'] == '1000000'
    assert result['extensions']['example']['info']['job'] == '123'


@pytest.mark.parametrize('change', [lambda o:o.update(x402Version=1),
    lambda o:o.update(x402Version=True), lambda o:o.update(accepts=[]),
    lambda o:o['resource'].update(url='https://attacker.example'),
    lambda o:o['accepts'][0].update(amount='0'), lambda o:o['accepts'][0].update(amount='1.2'),
    lambda o:o['accepts'][0].update(amount='-1'),lambda o:o['accepts'][0].update(maxTimeoutSeconds=0)])
def test_rejects_invalid_or_rebound_offers(change):
    o=offer(); change(o)
    with pytest.raises(ValueError): parse_offer(header(o), URL)


@pytest.mark.parametrize('url', ['http://localhost/private', 'file:///etc/passwd', 'https://user:pass@example.com', URL+'#other'])
def test_requires_https_resource_without_credentials(url):
    o=offer(); o['resource']['url']=url
    with pytest.raises(ValueError): parse_offer(header(o), url)


@pytest.mark.parametrize('encoded',['not base64', 'e30=', 'A'*32769])
def test_rejects_bad_headers(encoded):
    with pytest.raises(ValueError): parse_offer(encoded, URL)


@pytest.mark.parametrize('dry_run',['1','0'])
def test_review_is_bound_to_real_router_but_never_executable(setup, monkeypatch, dry_run):
    router, backend, queue=setup
    p=propose_offer(router,buyer='buyer',seller='seller',purpose='Buy specialist review',
        payment_required=header(offer()),resource_url=URL)
    assert p['status']=='pending'
    assert len(queue.proposals)==1
    assert p['path'][0]['asset']=='USDCOIN'
    assert router.state.read(p['id'])['x402']['offer']==offer()
    assert any(f.startswith('POLICY_BLOCK') for f in p['flags'])
    queue.proposals[p['id']]['status']='approved'
    monkeypatch.setenv('DRY_RUN',dry_run)
    with pytest.raises(ApprovalError,match='Policy-blocked'): router.execute(p['id'])
    # Stripping a warning cannot unlock an approved offer either.
    queue.proposals[p['id']]['flags']=[]
    with pytest.raises(ApprovalError,match='warnings'): router.execute(p['id'])
    assert backend.submissions==[]


@pytest.mark.parametrize('field,value',[('payTo','attacker'),('asset','unknown-mint'),
    ('network','eip155:8453'),('scheme','upto'),('extra',{})])
def test_untrusted_offer_cannot_change_allowed_recipient_or_asset(setup,field,value):
    router, backend, queue=setup
    o=offer(); o['accepts'][0][field]=value
    with pytest.raises(ValueError): propose_offer(router,buyer='buyer',seller='seller',purpose='Review',payment_required=header(o),resource_url=URL)
    assert queue.proposals=={}
    assert backend.submissions==[]
