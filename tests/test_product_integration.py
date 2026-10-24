"""Exercise Person C's actual fetched queue with fake money only."""
from decimal import Decimal
import importlib.util
import sys
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from runway_money.queue import HTTPQueue, ApprovalError
from runway_money.router import PaymentRouter
from runway_money.state import State
from test_money import Backend


@pytest.fixture
def integrated(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    folder = root / 'product' / 'queue_service'
    monkeypatch.syspath_prepend(str(folder))
    monkeypatch.setenv('STUB_EXECUTOR', '0')
    monkeypatch.setenv('QUEUE_DATA_FILE', str(tmp_path / 'queue.json'))
    monkeypatch.setenv('DRY_RUN', '1')
    spec = importlib.util.spec_from_file_location('test_product_queue', folder / 'app.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    with TestClient(module.app) as client:
        queue = HTTPQueue(client=client)
        backend = Backend()
        router = PaymentRouter(backend, queue, {'seller': {'accepted_asset_ids': ['usd']}},
                               state=State(tmp_path / 'plans'), prices=lambda asset: Decimal(1))
        yield router, backend, client


def test_real_product_queue_preserves_human_gate_and_dry_run(integrated):
    router, backend, client = integrated
    p = router.propose_payment('buyer', 'seller', 1, 'Buy data', 'human request')
    assert 'created_at' in p and p['path'][0]['amount'] == 1.0
    with pytest.raises(ApprovalError): router.execute(p['id'])
    # This is a test-only human decision against an isolated temporary queue.
    result = client.post(f'/proposals/{p["id"]}/decision', json={'decision':'approve', 'reason':'test human'})
    assert result.status_code == 200
    assert router.execute(p['id'])['status'] == 'approved'
    stored = client.get(f'/proposals/{p["id"]}').json()
    assert stored['status'] == 'approved' and 'receipt' not in stored
    assert backend.submissions == []


def test_real_product_queue_accepts_receipt_and_duplicate_repost(integrated, monkeypatch):
    router, backend, client = integrated
    p = router.propose_payment('buyer', 'seller', 1, 'Buy data', 'human request')
    client.post(f'/proposals/{p["id"]}/decision', json={'decision':'approve', 'reason':'test human'})
    monkeypatch.setenv('DRY_RUN', '0')
    first = router.execute(p['id'])
    assert first['status'] == 'executed'
    # Product rejects a second POST after execution; HTTPQueue avoids it.
    assert router.execute(p['id']) == first
    assert backend.submissions == ['transfers']


def test_removed_warning_blocks_execution_but_added_verifier_warning_is_allowed(integrated):
    router, backend, client = integrated
    p = router.propose_payment('buyer', 'seller', 1, 'Buy data', 'human request')
    plan = router.state.read(p['id'])
    current = dict(p, status='approved')
    current['flags'] = p['flags'] + ['VERIFIER_WARNING: verify purpose']
    router.queue.approved = lambda ident: current
    assert router._approved(p['id'], plan)['status'] == 'approved'
    current['flags'] = []
    with pytest.raises(ApprovalError, match='warnings'):
        router._approved(p['id'], plan)
