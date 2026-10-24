from types import SimpleNamespace
from agent.models import Proposal
from agent.payments import propose_and_enqueue
from agent.policy import PolicyConfig, _VELOCITY
from runway_money.agent_adapter import draft_payment
import pytest
from test_money import setup


def test_live_agent_drafts_checks_real_path_and_enqueues_once(setup, monkeypatch):
    router, backend, queue = setup
    monkeypatch.setenv('RUNWAY_MODE', 'live')
    monkeypatch.setattr('runway_money.agent_adapter.get_router', lambda: router)
    monkeypatch.setattr('agent.payments.verify', lambda **kwargs:
                        SimpleNamespace(is_mismatch=True, flag_text=lambda:'VERIFIER: test warning'))
    calls = []
    class ModelQueue:
        def create(self, p):
            calls.append(p)
            return Proposal.model_validate(queue.create(p.model_dump(mode='json')))
    policy = PolicyConfig(agent_id='live-adapter-test', asset_allowlist={'USDCOIN'},
                          recipient_allowlist={'seller'})
    _VELOCITY.pop(policy.agent_id, None)
    p, result, verifier = propose_and_enqueue(buyer='buyer', seller='seller', amount_usd=1,
        purpose='Purchase data', source='user message', user_request='Buy data', policy=policy,
        queue=ModelQueue())
    assert result.ok and len(calls) == 1 and len(queue.proposals) == 1
    assert p.path[0].asset == 'USDCOIN' and 'VERIFIER: test warning' in p.flags
    assert len(_VELOCITY[policy.agent_id]) == 1
    queue.proposals[p.id]['status'] = 'approved'
    assert router.execute(p.id)['quote']['dry_run']
    assert backend.submissions == []


def test_live_agent_blocks_actual_asset_not_in_policy(setup, monkeypatch):
    router, _, queue = setup
    monkeypatch.setenv('RUNWAY_MODE', 'live')
    monkeypatch.setattr('runway_money.agent_adapter.get_router', lambda: router)
    policy = PolicyConfig(agent_id='blocked-real-asset', asset_allowlist={'USDC','ETH'})
    p, result, verifier = propose_and_enqueue(buyer='buyer', seller='seller', amount_usd=1,
        purpose='Buy data', source='user message', user_request='Buy data', policy=policy,
        queue=object())
    assert p is None and result.blocked and verifier is None
    assert queue.proposals == {}


def test_fixed_transfer_fee_does_not_mask_excessive_swap_cost():
    from agent.policy import check_proposal
    policy=PolicyConfig(agent_id='fee-budget',max_single_payment_usd=5,asset_allowlist={'PYUSD'})
    args=dict(config=policy,buyer='test',seller='test2',amount_usd=5,assets_in_path=['PYUSD'],
              purpose='Pay seller',source='human request',transfer_fee_usd=1,record_velocity=False)
    assert check_proposal(**args,expected_cost=1).ok
    assert check_proposal(**args,expected_cost=1.2).blocked
