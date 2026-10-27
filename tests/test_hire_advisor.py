import json
import pytest
from product.queue_service.hire_advisor import recommend

CATALOG = [{'id': 'filings', 'name': 'Filings', 'price_usd': .05, 'simulated': True},
           {'id': 'archive', 'name': 'Archive', 'price_usd': .25},
           {'id': 'inactive', 'active': False}]


def answer(ids):
    return json.dumps({'comparison': 'Filings cover disclosures; archive covers history.', 'options': [
        {'specialist_id': i, 'reason': 'Relevant coverage', 'strengths': 'Listed coverage',
         'weaknesses': 'Accuracy is unverified'} for i in ids]})


def test_recommendations_are_grounded_and_preserve_rank():
    def chat(messages, **kwargs):
        assert kwargs['require_live'] is True
        evidence = json.loads(messages[1]['content'])
        assert len(evidence['catalog']) == 2
        assert 'owner_token_hash' not in messages[1]['content']
        return answer(['archive', 'filings'])
    result = recommend('Compare company research', [{**CATALOG[0], 'owner_token_hash': 'secret'}, *CATALOG[1:]], chat)
    assert [o['specialist_id'] for o in result['options']] == ['archive', 'filings']
    assert result['options'][0]['listing']['price_usd'] == .25


@pytest.mark.parametrize('ids', [['invented'], ['inactive'], ['filings', 'filings'], ['filings'] * 4])
def test_invalid_model_selections_are_rejected(ids):
    with pytest.raises(ValueError):
        recommend('Compare company research', CATALOG, lambda *a, **k: answer(ids))


def test_fewer_relevant_options_are_not_padded():
    result = recommend('Compare company research', CATALOG, lambda *a, **k: answer(['filings']))
    assert len(result['options']) == 1


def test_no_match_is_allowed():
    assert recommend('Unrelated question', CATALOG, lambda *a, **k: answer([]))['options'] == []


def test_no_catalog_does_not_call_model():
    assert recommend('Compare company research', [], lambda *a, **k: pytest.fail('Unexpected model call'))['options'] == []


def test_payment_preparation_never_approves_and_is_idempotent(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from product.queue_service.hire_advisor import install_purchase
    import sys
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path('product/queue_service').resolve()))
    monkeypatch.setenv('RUNWAY_MODE', 'stub')
    state = {'balances': {'buyer': {}}}
    class Store:
        def __enter__(self): return state
        def __exit__(self, *args): pass
    calls = []
    def enqueue(**kwargs):
        calls.append(kwargs)
        assert kwargs['seller'] == 'filings'
        assert kwargs['amount_usd'] == .05
        return SimpleNamespace(id='pending-proposal'), None, None
    monkeypatch.setattr('agent.payments.propose_and_enqueue', enqueue)
    app = FastAPI()
    install_purchase(app, lambda: [{**CATALOG[0], 'accepts': ['USDC']}], Store, None)
    client = TestClient(app)
    body = {'question': 'Review the company filings', 'specialist_id': 'filings', 'buyer': 'buyer', 'request_id': '12345678-1234-1234-1234-123456789abc'}
    assert client.post('/hire/prepare-payment', json=body).json()['proposal_id'] == 'pending-proposal'
    assert client.post('/hire/prepare-payment', json=body).status_code == 200
    assert len(calls) == 1
    assert state['hire_attempts'][body['request_id']]['status'] == 'pending_approval'
    assert client.post('/hire/prepare-payment', json={**body, 'question': 'A completely different request'}).status_code == 409
    monkeypatch.setenv('RUNWAY_MODE', 'live')
    assert client.post('/hire/prepare-payment', json=body).status_code == 409
