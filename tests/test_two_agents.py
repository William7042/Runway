from types import SimpleNamespace
import os
import pytest

from demo.two_agents import Runs, work, require_paid, deliver


def make_run():
    import uuid
    return {'id': str(uuid.uuid4()), 'question': 'Review the demo payment flow', 'events': [],
            'status': 'starting', 'proposal_id': None, 'receipt': None, 'answer': None}


def paid(run):
    p = {'id': 'p1', 'buyer': 'test', 'seller': 'test2', 'amount_usd': 4,
         'source': 'user:two-agents:' + run['id'], 'status': 'executed'}
    receipt = {'status': 'executed', 'tx_hash': 'chain-hash',
               'fill': {'execution_quality': {'actual_received': '4', 'expected_received': '4', 'shortfall': '0'}}}
    return p, receipt


@pytest.mark.parametrize('change', [dict(status='approved'), dict(seller='other'),
    dict(buyer='other'), dict(amount_usd=5), dict(source='different-job'), dict(id='different')])
def test_delivery_requires_exact_executed_invoice(change):
    run = make_run(); run['proposal_id'] = 'p1'
    p, receipt = paid(run); p.update(change)
    with pytest.raises(ValueError): require_paid(run, p, receipt)


@pytest.mark.parametrize('receipt', [dict(status='executed', tx_hash=None),
    dict(status='approved', tx_hash='hash'), dict(status='executed', tx_hash='hash',
    fill={'execution_quality': {'actual_received': '3'}})])
def test_unpaid_or_short_payment_never_delivers(receipt):
    run = make_run(); run['proposal_id'] = 'p1'; p, _ = paid(run)
    with pytest.raises(ValueError): require_paid(run, p, receipt)


def test_wait_then_external_approval_then_payment_then_two_roles(tmp_path, monkeypatch):
    monkeypatch.setenv('RUNWAY_MODE', 'live')
    store = Runs(tmp_path); run = make_run(); calls = []
    p, receipt = paid(run); p['status'] = 'pending'
    class Queue:
        def get(self, ident): return p.copy()
    class Router:
        queue = Queue()
        def execute(self, ident):
            assert p['status'] == 'approved'
            calls.append('execute'); p['status'] = 'executed'; return receipt
    def chat(messages, **kwargs):
        calls.append(messages[0]['content'])
        assert kwargs['require_live']
        if len(calls) == 1: return '{"plan":"Hire reviewer", "purpose":"Review the demo payment flow"}'
        return 'review answer'
    def sleep(_):
        assert 'execute' not in calls
        p['status'] = 'approved'  # Only an external human changes queue state.
    def enqueue(**kwargs):
        assert kwargs['source'] == 'user:two-agents:' + run['id']
        assert kwargs['amount_usd'] == 4
        return SimpleNamespace(id='p1'), None, SimpleNamespace(verdict='match', reason='aligned')
    work(run, store, router=Router(), sleep=sleep, chat=chat, enqueue=enqueue)
    assert run['status'] == 'complete'
    assert calls[1] == 'execute'
    assert 'specialist agent test2' in calls[2]
    assert 'buyer agent test' in calls[3]
    assert run['receipt']['tx_hash'] == 'chain-hash'


@pytest.mark.parametrize('status', ['rejected', 'failed'])
def test_rejection_never_executes_or_delivers(tmp_path, monkeypatch, status):
    monkeypatch.setenv('RUNWAY_MODE', 'live')
    run = make_run(); store = Runs(tmp_path); calls = []
    router = SimpleNamespace(queue=SimpleNamespace(get=lambda _: {'status': status}))
    def chat(*a, **kw): calls.append('plan'); return '{"plan":"review", "purpose":"review"}'
    work(run, store, router=router, chat=chat, enqueue=lambda **kw:
         (SimpleNamespace(id='p1'), None, SimpleNamespace(verdict='match', reason='aligned')))
    assert run['status'] == status
    assert calls == ['plan']


def test_dry_run_never_delivers_paid_work(tmp_path, monkeypatch):
    monkeypatch.setenv('RUNWAY_MODE', 'live')
    run = make_run(); store = Runs(tmp_path); calls = []
    router = SimpleNamespace(queue=SimpleNamespace(get=lambda _: {'status': 'approved'}),
        execute=lambda _: {'status': 'approved', 'tx_hash': None})
    def chat(*a, **kw): calls.append('plan'); return '{"plan":"review", "purpose":"review"}'
    work(run, store, router=router, chat=chat, enqueue=lambda **kw:
         (SimpleNamespace(id='p1'), None, SimpleNamespace(verdict='match', reason='aligned')))
    assert run['status'] == 'dry_run'
    assert calls == ['plan']


def test_delivery_retry_does_not_repay_or_repeat_specialist(tmp_path):
    run = make_run(); run['proposal_id'] = 'p1'; run['specialist_answer'] = 'previous answer'
    p, receipt = paid(run); run['receipt'] = receipt
    router = SimpleNamespace(queue=SimpleNamespace(get=lambda _: p))
    calls = []
    def chat(*a, **kw): calls.append('summary'); return 'final'
    deliver(run, Runs(tmp_path), router=router, chat=chat)
    assert calls == ['summary']
    assert run['answer'] == 'final'


def test_live_model_never_falls_back_offline(monkeypatch):
    from agent import llm
    monkeypatch.setattr(llm, '_client', lambda: None)
    with pytest.raises(RuntimeError, match='xAI key'):
        llm.chat([{'role': 'user', 'content': 'review'}], require_live=True)


def test_sdk_errors_never_expose_request_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv('RUNWAY_MODE', 'live')
    run = make_run()
    class Rejected(Exception):
        status_code = 400
    def chat(*a, **kw): raise Rejected('secret-request-content')
    work(run, Runs(tmp_path), chat=chat)
    assert run['status'] == 'failed'
    assert 'Model API rejected' in run['events'][-1]['text']
    assert 'secret-request-content' not in str(run)
