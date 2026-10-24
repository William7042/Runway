from copy import deepcopy
import pytest
from runway_money.assets import COMMERCE_SYMBOLS
from runway_money.queue import ApprovalError
from runway_money.router import PaymentRouter
from runway_money.state import State
from agent.policy import PolicyConfig
from test_money import Backend, Queue, USD, TOKEN, setup


def test_defaults_are_the_five_commerce_symbols(tmp_path):
    r=PaymentRouter(Backend(),Queue(),{},state=State(tmp_path))
    assert r.allowed_symbols==COMMERCE_SYMBOLS=={'USDC','PYUSD','SOL','BTC','ETH'}
    assert PolicyConfig(agent_id='agent').asset_allowlist==COMMERCE_SYMBOLS


def test_payment_rejects_outside_seller_asset_before_enqueue(setup):
    r,b,q=setup
    r.allowed_symbols=COMMERCE_SYMBOLS
    with pytest.raises(ValueError,match='allowlist'):
        r.propose_payment('buyer','seller',1,'Buy service','human request')
    assert not q.proposals and not b.submissions


@pytest.mark.parametrize('operation',['swap','top_up'])
def test_explicit_trades_reject_outside_assets_before_preparation(setup,operation):
    r,b,q=setup; r.allowed_symbols=COMMERCE_SYMBOLS
    with pytest.raises(ValueError,match='allowlist'):
        if operation=='swap': r.propose_swap('buyer','usd','token',1,1,'Trade','human request')
        else: r.propose_top_up('buyer','token',0.5,1,'Top up','human request')
    assert not b.preparations and not b.submissions and not q.proposals


def test_removed_asset_blocks_existing_approval(setup):
    r,b,q=setup
    p=r.propose_payment('buyer','seller',1,'Buy service','human request')
    q.proposals[p['id']]['status']='approved'
    r.allowed_symbols=COMMERCE_SYMBOLS
    with pytest.raises(ApprovalError,match='allowlist'): r.execute(p['id'])
    assert not b.submissions


def test_disallowed_holdings_are_not_sold_to_fund_purchase(setup,monkeypatch):
    r,b,q=setup
    usdc={**USD,'symbol':'USDC'}
    meme={**TOKEN,'symbol':'MEME'}
    monkeypatch.setattr(b,'assets',lambda:[deepcopy(usdc),deepcopy(meme)])
    b.holdings=[dict(asset_id='usd',available='10',total='10'),dict(asset_id='token',available='1000',total='1000')]
    r.allowed_symbols=COMMERCE_SYMBOLS
    def quote(*args): raise AssertionError('Disallowed holding must never be quoted')
    monkeypatch.setattr(b,'quote',quote)
    p=r.propose_payment('buyer','seller',1,'Buy service','human request')
    assert p['path']==[{'type':'transfer','asset':'USDC','amount':'1.000000'}]


def test_mcp_stub_proposes_only_supported_symbols():
    from stubs.router_stub import propose_payment
    p=propose_payment('buyer','seller',1,'Review','human request')
    assert all(step.asset in COMMERCE_SYMBOLS for step in p.path)
    assert any('SIMULATED' in flag for flag in p.flags)
