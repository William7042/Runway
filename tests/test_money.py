from copy import deepcopy
from decimal import Decimal
import json
import httpx
import pytest
from runway_money.queue import HTTPQueue, ApprovalError
from runway_money.router import PaymentRouter
from runway_money.state import State
from runway_money.stub import StubRouter
from runway_money.treasury import remaining_basis, spendable_gains, top_up_budget
from runway_money.prices import drift_bps
from runway_money.backend import TrueMarketsBackend


USD = dict(id='usd', symbol='USDCOIN', chain='solana', address='usd-mint',
           decimals=6, stable=True, is_active=True, tradeable=False, venue='defi')
TOKEN = dict(id='token', symbol='TOKEN', chain='solana', address='token-mint',
             decimals=6, stable=False, is_active=True, tradeable=True, venue='defi')


class Queue:
    def __init__(self):
        self.proposals, self.receipts = {}, {}
        self.fail_receipt = False

    def create(self, p):
        self.proposals[p['id']] = deepcopy(p)
        return deepcopy(p)

    def approved(self, ident):
        p = self.proposals[ident]
        if p['status'] != 'approved':
            raise ApprovalError('Human approval required')
        return deepcopy(p)

    def receipt(self, ident, receipt):
        if self.fail_receipt:
            raise ConnectionError('queue down')
        self.receipts[ident] = deepcopy(receipt)


class Backend:
    def __init__(self):
        self.holdings = [dict(asset_id='usd', available='10', total='10')]
        self.submissions = []
        self.preparations = []
        self.fail_confirm = False
        self.transfer_fee = '0'
        self.transfer_to = None

    def assets(self):
        return [deepcopy(USD), deepcopy(TOKEN)]

    def balances(self, buyer):
        return self.holdings

    def recipient(self, seller, chain):
        return 'registered-recipient'

    def quote(self, buyer, source, target, quantity):
        output = quantity * Decimal('0.999')
        return dict(input=str(quantity), output=str(output), fee='0.001',
                    fee_asset_id='usd', raw={'base_asset': 'token-mint', 'quote_asset': 'usd-mint', 'fee_asset': 'usd-mint'},
                    order_body={'venue': 'defi'})

    def prepare_order(self, buyer, quote):
        self.preparations.append('order')
        return {'order_id': 'order1', 'quote': {'qty_out': quote['output'],
                'qty': quote['input'], 'base_asset': 'token-mint', 'quote_asset': 'usd-mint',
                'fee_asset': 'usd-mint', 'fee': '0.001'}}

    def prepare_transfer(self, buyer, asset_id, quantity, recipient):
        self.preparations.append('transfer')
        return dict(id='transfer1', asset_id=asset_id, qty=str(quantity),
                    qty_unit='base', to=self.transfer_to or recipient,
                    chain='solana', fee=self.transfer_fee)

    def submit(self, buyer, kind, prepared, guard):
        guard()
        self.submissions.append(kind)

    def confirm(self, buyer, kind, ident):
        if self.fail_confirm:
            raise TimeoutError('uncertain chain state')
        return {'status': 'completed' if kind == 'transfers' else 'complete', 'tx_hash': 'real-chain-hash',
                'fee': '0', 'received': '1', 'sent': '1'}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('DRY_RUN', '1')
    backend, queue = Backend(), Queue()
    router = PaymentRouter(backend, queue, {'seller': {'accepted_asset_ids': ['usd']}},
                           allowed_symbols={'USDCOIN', 'TOKEN'}, state=State(tmp_path), prices=lambda asset: Decimal(1), payment_fee_budget_usd='0')
    return router, backend, queue


def propose(router):
    return router.propose_payment('buyer', 'seller', '1', 'Purchase data', 'user requested data')


def approve(queue, p):
    # Test fixture models an external human decision. Production code has no such operation.
    queue.proposals[p['id']]['status'] = 'approved'


def test_stub_contract_and_approval(setup):
    _, _, queue = setup
    stub = StubRouter(queue)
    p = propose(stub)
    assert set(p) == {'id','buyer','seller','purpose','amount_usd','path','expected_cost',
                      'alternatives','drift','flags','source','status'}
    with pytest.raises(ApprovalError):
        stub.execute(p['id'])
    approve(queue, p)
    r = stub.execute(p['id'])
    assert r['tx_hash'] is None and r['fill']['simulated']


@pytest.mark.parametrize('amount', ['0', '-1', 'NaN', 'Infinity', '1.01'])
def test_invalid_or_over_cap_amount_rejected(setup, amount):
    router, _, _ = setup
    with pytest.raises(ValueError):
        router.propose_payment('buyer', 'seller', amount, 'data', 'user')


def test_pending_rejected_and_modified_proposals_cannot_execute(setup, monkeypatch):
    router, backend, queue = setup
    p = propose(router)
    with pytest.raises(ApprovalError):
        router.execute(p['id'])
    queue.proposals[p['id']]['status'] = 'rejected'
    with pytest.raises(ApprovalError):
        router.execute(p['id'])
    approve(queue, p)
    queue.proposals[p['id']]['amount_usd'] = 0.5
    with pytest.raises(ApprovalError):
        router.execute(p['id'])
    assert backend.submissions == []


def test_dry_run_never_prepares_signs_posts_receipt_or_consumes_approval(setup):
    router, backend, queue = setup
    p = propose(router)
    approve(queue, p)
    receipt = router.execute(p['id'])
    assert receipt['status'] == 'approved' and receipt['quote']['dry_run']
    assert receipt['tx_hash'] is None and receipt['fill'] is None
    assert backend.preparations == backend.submissions == []
    assert queue.receipts == {}
    assert router.state.read(p['id'])['phase'] == 'pending'


def test_live_transfer_confirms_and_never_pays_twice(setup, monkeypatch):
    router, backend, queue = setup
    p = propose(router)
    approve(queue, p)
    monkeypatch.setenv('DRY_RUN', '0')
    receipt = router.execute(p['id'])
    assert receipt['status'] == 'executed' and receipt['tx_hash'] == 'real-chain-hash'
    assert router.execute(p['id']) == receipt
    assert backend.submissions == ['transfers']


def test_queue_receipt_failure_can_be_reposted_without_repaying(setup, monkeypatch):
    router, backend, queue = setup
    p = propose(router)
    approve(queue, p)
    monkeypatch.setenv('DRY_RUN', '0')
    queue.fail_receipt = True
    with pytest.raises(ConnectionError):
        router.execute(p['id'])
    queue.fail_receipt = False
    assert router.execute(p['id'])['status'] == 'executed'
    assert backend.submissions == ['transfers']


def test_timeout_is_recorded_and_not_resubmitted(setup, monkeypatch):
    router, backend, queue = setup
    p = propose(router)
    approve(queue, p)
    backend.fail_confirm = True
    monkeypatch.setenv('DRY_RUN', '0')
    r = router.execute(p['id'])
    assert r['status'] == 'failed' and r['fill']['needs_reconciliation']
    router.execute(p['id'])
    assert backend.submissions == ['transfers']


@pytest.mark.parametrize('change', ['recipient', 'fee'])
def test_changed_destination_or_added_fee_stops_before_signing(setup, monkeypatch, change):
    router, backend, queue = setup
    p = propose(router)
    approve(queue, p)
    if change == 'recipient': backend.transfer_to = 'attacker'
    else: backend.transfer_fee = '0.01'
    monkeypatch.setenv('DRY_RUN', '0')
    assert router.execute(p['id'])['status'] == 'failed'
    assert backend.submissions == []


def test_lowest_cost_path_prefers_pay_in_kind(setup):
    router, backend, _ = setup
    backend.holdings.append(dict(asset_id='token', available='10', total='10'))
    p = propose(router)
    assert len(p['path']) == 1 and p['expected_cost'] == 0
    assert any('Higher' in a['rejected_reason'] for a in p['alternatives'])


def test_price_impact_rejects_expensive_path(setup):
    router, backend, _ = setup
    backend.holdings = [dict(asset_id='token', available='10', total='10')]
    router.max_impact = Decimal('1')
    with pytest.raises(ValueError, match='Price impact'):
        propose(router)


def test_endowment_never_treats_missing_history_as_gains(setup):
    router, backend, _ = setup
    router.modes = {'buyer': 'endowment'}
    backend.history = lambda buyer: []
    with pytest.raises(ValueError, match='principal'):
        propose(router)


def test_weighted_basis_and_gains_preserve_principal():
    rows = [dict(asset_id='token', action='buy', quantity='10', value_usd='80', fee_usd='2', timestamp=1),
            dict(asset_id='token', action='sell', quantity='2', value_usd='20', fee_usd='0', timestamp=2)]
    assert remaining_basis(rows, 'token', 8) == Decimal('65.6')
    assert spendable_gains(rows, 'token', 8, 10) == Decimal('14.4')
    with pytest.raises(ValueError): remaining_basis(rows, 'token', 9)


def test_drift_and_top_up_sizing():
    assert drift_bps(110, 100) == 1000
    assert top_up_budget(100, 20, '.5', 10) == 10
    assert top_up_budget(100, 70, '.5', 10) == 0


def test_http_queue_uses_contract_list_endpoint():
    requests = []
    def respond(req):
        requests.append((req.method, req.url.path))
        return httpx.Response(200, json=[{'id':'p', 'status':'approved'}])
    queue = HTTPQueue(client=httpx.Client(base_url='http://test', transport=httpx.MockTransport(respond)))
    assert queue.approved('p')['id'] == 'p'
    assert requests == [('GET', '/proposals')]


def test_sdk_quote_rejects_silent_bridge_or_different_settlement_asset():
    class Client:
        def lookup_user(self, name): return {'user_id': 'uid'}
        def request(self, *args, **kwargs):
            return {'quote_asset': 'different-mint', 'base_asset': 'token-mint',
                    'qty_out': '1', 'fee_asset': 'usd-mint', 'fee': '0', 'issues': []}
    backend = TrueMarketsBackend(Client())
    with pytest.raises(ValueError, match='settlement asset'):
        backend.quote('buyer', USD, TOKEN, Decimal(1))


def test_backend_dry_run_blocks_signing_even_with_approval(monkeypatch):
    monkeypatch.setenv('DRY_RUN', '1')
    backend = TrueMarketsBackend(client=object())
    with pytest.raises(RuntimeError, match='DRY_RUN'):
        backend.submit('buyer', 'orders', {}, lambda: None)


def test_drift_slider_switches_simulated_payment_to_stablecoin(setup):
    _, _, queue = setup
    stub = StubRouter(queue, on_chain_price=120, reference_price=100)
    p = propose(stub)
    assert p['path'] == [{'type': 'transfer', 'asset': 'USDC', 'amount': '1'}]
    assert p['drift']['bps'] == 2000
    assert p['alternatives'] and any('SIMULATED' in flag for flag in p['flags'])


def test_approval_revocation_between_preparation_and_signing_stops_payment(setup, monkeypatch):
    router, backend, queue = setup
    p = propose(router)
    approve(queue, p)
    original = backend.prepare_transfer
    def revoke(*args):
        prepared = original(*args)
        queue.proposals[p['id']]['status'] = 'rejected'
        return prepared
    backend.prepare_transfer = revoke
    monkeypatch.setenv('DRY_RUN', '0')
    assert router.execute(p['id'])['status'] == 'failed'
    assert backend.submissions == []


def test_swap_timeout_never_transfers_or_resubmits(setup, monkeypatch):
    router, backend, queue = setup
    backend.holdings = [dict(asset_id='token', available='10', total='10')]
    p = propose(router)
    approve(queue, p)
    backend.fail_confirm = True
    monkeypatch.setenv('DRY_RUN', '0')
    r = router.execute(p['id'])
    assert r['status'] == 'failed'
    assert backend.submissions == ['orders']
    assert backend.preparations == ['order']
    router.execute(p['id'])
    assert backend.submissions == ['orders']


def test_swap_fills_then_transfers_exact_approved_quantity(setup, monkeypatch):
    router, backend, queue = setup
    backend.holdings = [dict(asset_id='token', available='10', total='10')]
    p = propose(router)
    approve(queue, p)
    original = backend.confirm
    def settle(buyer, kind, ident):
        if kind == 'orders':
            backend.holdings.append(dict(asset_id='usd', available='1.001', total='1.001'))
        return original(buyer, kind, ident)
    backend.confirm = settle
    monkeypatch.setenv('DRY_RUN', '0')
    r = router.execute(p['id'])
    assert r['status'] == 'executed'
    assert backend.submissions == ['orders', 'transfers']
    assert len(r['fill']['operations']) == 2


def test_second_process_lock_blocks_duplicate_execution(setup):
    router, _, queue = setup
    p = propose(router)
    approve(queue, p)
    with router.state.lock(p['id']):
        with pytest.raises(BlockingIOError):
            router.execute(p['id'])


def test_organization_auth_accepts_token_without_refresh(monkeypatch):
    from runway_money.client import RunwayClient
    monkeypatch.setenv('TM_TELEMETRY', '0')
    monkeypatch.setattr('runway_money.client.load_key_file', lambda path: ('key-id', object()))
    monkeypatch.setattr('runway_money.client.sign_challenge', lambda *args: 'challenge-signature')
    monkeypatch.setattr('runway_money.client.httpx.post', lambda *args, **kwargs:
                        httpx.Response(200, json={'access_token': 'test-token', 'expires_in': 3600}))
    with RunwayClient(key_file='unused') as client:
        client.authenticate()
        assert client._access_token == 'test-token' and client._refresh_token is None
        with pytest.raises(RuntimeError, match='approval-guarded'):
            client.sign_turnkey('unsigned payload')


def test_limit_buy_back_requires_approval_and_dry_run_never_places_order(setup):
    router, backend, queue = setup
    backend.limit_preview = lambda *args: {'price': '1', 'fee': '0'}
    p = router.propose_top_up('buyer', 'token', '.5', '1', 'Restore target allocation', 'human target allocation')
    with pytest.raises(ApprovalError): router.execute(p['id'])
    approve(queue, p)
    receipt = router.execute(p['id'])
    assert receipt['status'] == 'approved' and receipt['quote']['dry_run']
    assert backend.submissions == []


def test_limit_resting_order_is_polled_without_resubmission(setup, monkeypatch):
    router, backend, queue = setup
    backend.limit_preview = lambda *args: {'price': '1', 'fee': '0'}
    placed = []
    def create(*args):
        placed.append('limit')
        return {'order_id': 'limit1', 'status': 'active'}
    backend.create_limit = create
    backend.read_order = lambda *args: {'status': 'active', 'executed_qty': '0'}
    p = router.propose_top_up('buyer', 'token', '.5', '1', 'Rebalance', 'human target')
    approve(queue, p)
    monkeypatch.setenv('DRY_RUN', '0')
    assert router.execute(p['id'])['status'] == 'approved'
    assert router.execute(p['id'])['status'] == 'approved'
    assert placed == ['limit'] and queue.receipts == {}
    backend.read_order = lambda *args: {'status': 'complete', 'executed_qty': '1', 'executed_vwap': '.99'}
    assert router.execute(p['id'])['status'] == 'executed'
    assert placed == ['limit']


def test_unquoted_fee_and_short_payment_fail_receipt_and_hold_future_execution(setup, monkeypatch):
    router, backend, queue = setup
    p = propose(router)
    approve(queue, p)
    backend.confirm = lambda *args: {'status': 'completed', 'tx_hash': 'confirmed-underpayment',
                                     'sent': '1', 'fee': '.2', 'received': '.8'}
    monkeypatch.setenv('DRY_RUN', '0')
    receipt = router.execute(p['id'])
    assert receipt['status'] == 'failed'
    assert receipt['tx_hash'] == 'confirmed-underpayment'
    assert receipt['fill']['execution_quality']['shortfall'] == '0.200000'
    another = propose(router)
    approve(queue, another)
    with pytest.raises(RuntimeError, match='hold'):
        router.execute(another['id'])
    assert backend.submissions == ['transfers']


def test_standalone_swap_requires_new_approval_and_audit_before_success(setup, monkeypatch):
    router, backend, queue = setup
    backend.prepare_swap = lambda *args: ('orders', {'order_id':'swap1','quote':{'qty_out':'1'}})
    backend.preflight = lambda *args: {'digest':'verified', 'native_delta':0}
    backend.audit_swap = lambda *args: {'matched_approved_bounds':True,'actual_input':'1','actual_output':'.999'}
    submit = backend.submit
    def submit_order(*args):
        submit(*args)
        return {'order_id':'swap1'}
    backend.submit = submit_order
    p = router.propose_swap('buyer','usd','token',1,'.995','Convert stablecoin','human request')
    with pytest.raises(ApprovalError): router.execute(p['id'])
    approve(queue,p)
    assert router.execute(p['id'])['quote']['dry_run']
    assert backend.submissions == []
    monkeypatch.setenv('DRY_RUN','0')
    r = router.execute(p['id'])
    assert r['status'] == 'executed' and r['fill']['execution_quality']['matched_approved_bounds']
    router.execute(p['id'])
    assert backend.submissions == ['orders']


def test_standalone_swap_failed_preflight_cannot_sign(setup, monkeypatch):
    router, backend, queue = setup
    backend.prepare_swap = lambda *args: ('orders', {'order_id':'swap1','quote':{'qty_out':'1'}})
    backend.preflight = lambda *args: {'digest':'verified'}
    p = router.propose_swap('buyer','usd','token',1,'.995','Convert stablecoin','human request')
    approve(queue,p)
    def fail(*args): raise ValueError('hidden debit')
    backend.preflight = fail
    monkeypatch.setenv('DRY_RUN','0')
    with pytest.raises(ValueError,match='hidden debit'):
        router.execute(p['id'])
    assert backend.submissions == [] and router.state.read(p['id'])['phase'] == 'pending'


def test_legacy_defi_trade_is_confirmed_by_chain_audit_not_gateway_lookup(setup, monkeypatch):
    router, backend, queue = setup
    backend.prepare_swap = lambda *args: ('trades', {'quote_id':'quote1','qty_out':'1'})
    backend.preflight = lambda *args: {'digest':'verified'}
    submit = backend.submit
    def trade(*args):
        submit(*args)
        return {'order_id':'legacy-id','tx_hash':'confirmed-legacy-tx','status':'FILLED'}
    backend.submit = trade
    def fail_lookup(*args): raise AssertionError('Legacy IDs do not belong to Gateway')
    backend.confirm = fail_lookup
    backend.audit_swap = lambda *args: {'matched_approved_bounds':True,'actual_input':'1','actual_output':'.999'}
    p=router.propose_swap('buyer','usd','token',1,'.995','Convert stablecoin','human request')
    approve(queue,p)
    monkeypatch.setenv('DRY_RUN','0')
    r=router.execute(p['id'])
    assert r['status']=='executed' and r['tx_hash']=='confirmed-legacy-tx'


def test_disclosed_one_dollar_fee_grosses_up_and_pays_full_invoice(setup, monkeypatch):
    router, backend, queue = setup
    router.max_payment = Decimal(5)
    router.payment_fee_budget = Decimal(1)
    backend.preview_transfer = lambda buyer, asset, qty, recipient: {
        'asset_id':asset,'to':recipient,'fee':'1','received':str(Decimal(str(qty))-1)}
    p = router.propose_payment('buyer','seller',5,'Pay seller','human request')
    assert p['amount_usd']==5 and p['expected_cost']==1 and p['path'][0]['amount']=='6.000000'
    assert any('Seller receives 5.000000' in flag for flag in p['flags'])
    approve(queue,p)
    backend.confirm = lambda *args: {'status':'completed','tx_hash':'grossed-up-tx',
                                    'sent':'6','received':'5','fee':'1'}
    monkeypatch.setenv('DRY_RUN','0')
    receipt=router.execute(p['id'])
    assert receipt['status']=='executed' and receipt['fill']['execution_quality']['shortfall']=='0'


def test_transfer_fee_above_one_dollar_remains_blocked(setup):
    router, backend, queue = setup
    router.payment_fee_budget = Decimal(1)
    backend.preview_transfer = lambda buyer, asset, qty, recipient: {
        'asset_id':asset,'to':recipient,'fee':'1.01','received':'0'}
    with pytest.raises(ValueError,match='fee budget'):
        propose(router)
    assert queue.proposals=={} and backend.submissions==[]


def test_releasing_hold_retains_evidence_and_new_mismatch_reblocks(setup):
    router, _, _ = setup
    router.state.hold({'reason':'original fee mismatch'})
    router.state.release_hold('Human authorized $1 transfer fee with net/gross checks')
    router.state.check_hold()
    assert router.state.read('__execution_hold__')['reason']=='original fee mismatch'
    router.state.hold({'reason':'new unapproved discrepancy'})
    with pytest.raises(RuntimeError,match='hold'): router.state.check_hold()
