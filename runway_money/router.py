"""Cost-ranked payments with immutable human-approved plans and durable execution."""
import json
import os
import time
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from uuid import uuid4
from .backend import TrueMarketsBackend, dry_run, public
from .queue import HTTPQueue, ApprovalError
from .state import State, fingerprint
from .prices import ReferencePrices, drift_bps
from .treasury import dec, spendable_gains, top_up_budget
from .client import TrueMarketsError


class PaymentRouter:
    def __init__(self, backend, queue, sellers, *, state=None, prices=None,
                 modes=None, max_payment_usd='1', max_impact_bps='100',
                 max_drift_bps='200', max_fee_usd='0.01', top_up_targets=None):
        self.backend, self.queue, self.sellers = backend, queue, sellers
        self.state, self.prices = state or State(), prices or ReferencePrices()
        self.modes = modes or {}
        self.max_payment = dec(max_payment_usd)
        self.max_impact = dec(max_impact_bps)
        self.max_drift = dec(max_drift_bps)
        self.max_fee = dec(max_fee_usd)
        self.top_up_targets = top_up_targets or {}

    def propose_payment(self, buyer, seller, amount_usd, purpose, source):
        return self._payment(buyer, seller, amount_usd, purpose, source, enqueue=True)

    def draft_payment(self, buyer, seller, amount_usd, purpose, source):
        """Agent adapter: policy and verifier finish before one queue creation."""
        return self._payment(buyer, seller, amount_usd, purpose, source, enqueue=False)

    def _payment(self, buyer, seller, amount_usd, purpose, source, *, enqueue):
        amount = dec(amount_usd)
        if amount <= 0 or amount > self.max_payment:
            raise ValueError('Payment must be positive and within configured demo cap')
        if not purpose or not source:
            raise ValueError('Plain-English purpose and request source are required')
        catalog = {a['id']: a for a in self.backend.assets() if a.get('is_active')}
        policy = self.sellers[seller]  # Registered recipient/accepted-asset allowlist.
        accepted = [catalog[a] for a in policy['accepted_asset_ids']]
        holdings = self.backend.balances(buyer)
        mode = self.modes.get(buyer, 'pay_in_kind')
        if mode not in {'pay_in_kind', 'endowment', 'auto_top_up'}:
            raise ValueError('Unknown treasury mode')
        if mode == 'auto_top_up' and buyer not in self.top_up_targets:
            raise ValueError('Auto top-up needs an explicit target allocation and limit price')
        candidates, alternatives = [], []
        for holding in holdings:
            if dec(holding['available']) <= 0 or holding['asset_id'] not in catalog:
                continue
            held = catalog[holding['asset_id']]
            for target in accepted:
                path = [{'type': 'swap', 'asset': held['symbol'], 'amount': '0'},
                        {'type': 'transfer', 'asset': target['symbol'], 'amount': '0'}]
                try:
                    if held.get('venue') != 'defi' or target.get('venue') != 'defi':
                        raise ValueError('Demo transfers require on-chain DeFi assets')
                    if held['chain'] != target['chain']:
                        raise ValueError('Cross-chain payment route is unavailable')
                    if mode == 'auto_top_up' and not held.get('stable'):
                        raise ValueError('Auto top-up payments spend stablecoin only')
                    hp, tp = dec(self.prices(held)), dec(self.prices(target))
                    if hp <= 0 or tp <= 0:
                        raise ValueError('Positive reference prices required')
                    quantum = Decimal(10) ** -target['decimals']
                    pay_qty = (amount / tp).quantize(quantum, rounding=ROUND_DOWN)
                    if pay_qty <= 0:
                        raise ValueError('Payment rounds to zero')
                    flags = []
                    if held.get('stable') or target.get('stable'):
                        flags.append('Demo stablecoin USD reference assumes $1; depeg risk is not priced')
                    quote, drift = None, None
                    transfer_fee = Decimal(0)
                    address = policy.get('address') or self.backend.recipient(seller, target['chain'])
                    if held['id'] == target['id']:
                        input_qty, cost = pay_qty, Decimal(0)
                        path = [{'type': 'transfer', 'asset': target['symbol'], 'amount': str(pay_qty)}]
                        if hasattr(self.backend, 'preview_transfer'):
                            preview = self.backend.preview_transfer(buyer, target['id'], pay_qty, address)
                            if preview['to'] != address or preview['asset_id'] != target['id']:
                                raise ValueError('Transfer preview changed the destination or asset')
                            transfer_fee = dec(preview['fee']) * tp
                            cost += transfer_fee
                            if dec(preview['received']) < pay_qty:
                                raise ValueError(f'Transfer would deliver {preview["received"]} {target["symbol"]} '
                                    f'for a {pay_qty} invoice; simulated fee {preview["fee"]}. '
                                    'A separately approved gross-up and fee budget are required')
                    else:
                        input_qty = (amount / hp).quantize(Decimal(10) ** -held['decimals'], rounding=ROUND_UP)
                        quote = self.backend.quote(buyer, held, target, input_qty)
                        # Size to fund the invoice, including fee and a small rounding buffer.
                        if dec(quote['output']) < pay_qty:
                            input_qty *= pay_qty / dec(quote['output']) * Decimal('1.00001')
                            input_qty = input_qty.quantize(Decimal(10) ** -held['decimals'], rounding=ROUND_DOWN)
                            quote = self.backend.quote(buyer, held, target, input_qty)
                        if dec(quote['output']) < pay_qty:
                            raise ValueError('Quoted proceeds do not cover the payment')
                        fee_asset = catalog[quote['fee_asset_id']]
                        fee_usd = dec(quote['fee']) * dec(self.prices(fee_asset))
                        # Mark-to-reference cost bounds price impact plus service fee.
                        cost = max(Decimal(0), input_qty * hp - dec(quote['output']) * tp) + fee_usd
                        impact = cost / (input_qty * hp) * 10000
                        if impact > self.max_impact:
                            raise ValueError('Price impact plus fees exceeds policy limit')
                        path = [{'type': 'swap', 'asset': held['symbol'], 'amount': str(input_qty)},
                                {'type': 'transfer', 'asset': target['symbol'], 'amount': str(pay_qty)}]
                        stock = held if held.get('reference_symbol') else target if target.get('reference_symbol') else None
                        if stock:
                            on_chain = (dec(quote['output']) * tp / input_qty if stock is held
                                        else input_qty * hp / dec(quote['output']))
                            reference = hp if stock is held else tp
                            gap = drift_bps(on_chain, reference)
                            drift = {'on_chain_price': float(on_chain), 'reference_price': float(reference), 'bps': float(gap)}
                            if gap > self.max_drift:
                                raise ValueError('Stock price drift exceeds threshold; wait or pay from stablecoin')
                    if cost > self.max_fee:
                        raise ValueError('Estimated total cost exceeds demo fee budget')
                    input_quantum = Decimal(10) ** -held['decimals']
                    if input_qty != input_qty.quantize(input_quantum):
                        raise ValueError('Source quantity exceeds asset precision')
                    if input_qty > dec(holding['available']):
                        raise ValueError('Insufficient available holding')
                    if mode == 'endowment':
                        gains = spendable_gains(self.backend.history(buyer), held['id'], holding['total'], hp)
                        if input_qty * hp + cost > gains:
                            raise ValueError('Payment would consume principal rather than unrealized gains')
                    flags.append('Transfer fees must fit the approved cost; signing stops if they increase')
                    if mode == 'auto_top_up':
                        flags.append('Any allocation buy-back requires a separate human-approved limit order')
                    plan = {'source_asset': held, 'target_asset': target, 'recipient': address,
                            'input_qty': str(input_qty), 'pay_qty': str(pay_qty),
                            'transfer_fee_usd': str(transfer_fee),
                            'quote': quote, 'mode': mode, 'source_price': str(hp), 'target_price': str(tp)}
                    candidates.append((cost, path, plan, drift, flags))
                except (ValueError, KeyError, StopIteration, TrueMarketsError) as e:
                    alternatives.append({'path': path, 'rejected_reason': str(e) or 'Unavailable route'})
        if not candidates:
            raise ValueError('No safe payment path: ' + '; '.join(a['rejected_reason'] for a in alternatives))
        candidates.sort(key=lambda c: c[0])
        cost, path, plan, drift, flags = candidates[0]
        alternatives.extend({'path': c[1], 'rejected_reason': 'Higher estimated total cost'} for c in candidates[1:])
        if any('drift' in a['rejected_reason'].lower() for a in alternatives):
            flags.append('Stock route rejected for drift; selected a safer available holding')
        proposal = dict(id=str(uuid4()), buyer=buyer, seller=seller, purpose=purpose,
                        amount_usd=float(amount), path=path, expected_cost=float(cost),
                        alternatives=alternatives, drift=drift, flags=flags, source=source, status='pending')
        plan.update({'proposal': proposal, 'fingerprint': fingerprint(proposal),
                     'created_at': time.time(), 'phase': 'pending'})
        self.state.write(proposal['id'], plan)
        if not enqueue:
            return proposal
        returned = self.queue.create(proposal)
        if returned.get('status') != 'pending' or fingerprint(returned) != plan['fingerprint']:
            raise ApprovalError('Queue altered proposal or approved it without a human decision')
        return returned

    def _approved(self, proposal_id, plan):
        current = self.queue.approved(proposal_id)
        if fingerprint(current) != plan['fingerprint']:
            raise ApprovalError('Approved proposal differs from the original plan; propose again')
        flags = current.get('flags', [])
        if any(flag not in flags for flag in plan['proposal']['flags']):
            raise ApprovalError('Original safety warnings were removed')
        if any(str(flag).upper().startswith('POLICY_BLOCK') for flag in flags):
            raise ApprovalError('Policy-blocked proposals cannot execute')
        return current

    def execute(self, proposal_id):
        with self.state.lock(proposal_id):
            plan = self.state.read(proposal_id)
            # Completed results can be reposted after queue delivery failure, never repaid.
            if plan.get('receipt'):
                self.queue.receipt(proposal_id, plan['receipt'])
                return plan['receipt']
            self._approved(proposal_id, plan)
            if plan.get('kind') == 'swap':
                return self._execute_swap(proposal_id, plan)
            if plan.get('kind') == 'top_up':
                return self._execute_top_up(proposal_id, plan)
            if plan['phase'] != 'pending':
                raise RuntimeError('Execution already started; reconcile recorded operations before retrying')
            p = plan['proposal']
            if dry_run():
                # Status stays approved and no receipt is POSTed: a preview is not a fill.
                return {'quote': {'dry_run': True, 'path': p['path'],
                                  'recipient': plan['recipient'], 'expected_cost': p['expected_cost']},
                        'fill': None, 'tx_hash': None, 'status': 'approved'}
            self.state.check_hold()
            if time.time() - plan['created_at'] > 300:
                raise ValueError('Proposal expired; obtain a fresh proposal and human approval')
            buyer = p['buyer']
            guard = lambda: self._approved(proposal_id, plan)
            plan['phase'] = 'started'
            self.state.write(proposal_id, plan)
            try:
                fills = []
                quote = plan['quote']
                if quote:
                    fresh = self.backend.quote(buyer, plan['source_asset'], plan['target_asset'], dec(plan['input_qty']))
                    if dec(fresh['output']) < dec(plan['pay_qty']) or dec(fresh['fee']) > dec(quote['fee']):
                        raise ValueError('Quote worsened; fresh approval required')
                    guard()
                    prepared = self.backend.prepare_order(buyer, fresh)
                    plan['order'] = public(prepared)
                    self.state.write(proposal_id, plan)
                    current_quote = prepared.get('quote', {})
                    if not prepared.get('order_id') or current_quote.get('issues'):
                        raise ValueError('Order is not executable')
                    if (dec(current_quote['qty_out']) < dec(plan['pay_qty']) or
                        dec(current_quote['qty']) != dec(plan['input_qty']) or
                        current_quote.get('base_asset') != fresh['raw'].get('base_asset') or
                        current_quote.get('quote_asset') != fresh['raw'].get('quote_asset') or
                        current_quote.get('fee_asset') != fresh['raw'].get('fee_asset') or
                        current_quote.get('bridge_state') or
                        dec(current_quote['fee']) > dec(quote['fee'])):
                        raise ValueError('Prepared order exceeds approved quote bounds')
                    plan['phase'] = 'order_submitting'
                    if hasattr(self.backend, 'preflight'):
                        self.backend.preflight(buyer, 'orders', prepared, plan)
                    self.state.write(proposal_id, plan)
                    self.backend.submit(buyer, 'orders', prepared, guard)
                    fill = self.backend.confirm(buyer, 'orders', prepared['order_id'])
                    fills.append(fill)
                    plan['order_fill'] = fill
                    self.state.write(proposal_id, plan)
                    if fill['status'] != 'complete' or not fill.get('tx_hash'):
                        raise ValueError('Swap did not confirm on-chain; transfer stopped')
                guard()
                available = next((dec(b['available']) for b in self.backend.balances(buyer)
                                  if b['asset_id'] == plan['target_asset']['id']), Decimal(0))
                if available < dec(plan['pay_qty']):
                    raise ValueError('Insufficient confirmed balance for transfer')
                transfer = self.backend.prepare_transfer(buyer, plan['target_asset']['id'],
                                                         plan['pay_qty'], plan['recipient'])
                plan['transfer'] = public(transfer)
                self.state.write(proposal_id, plan)
                fee = dec(transfer['fee']) * dec(plan['target_price'])
                # Seller, asset, chain and quantity must match the reviewed plan.
                if (transfer['to'] != plan['recipient'] or transfer['asset_id'] != plan['target_asset']['id'] or
                    transfer['chain'] != plan['target_asset']['chain'] or
                    dec(transfer['qty']) != dec(plan['pay_qty']) or transfer['qty_unit'] != 'base' or
                    fee > dec(plan.get('transfer_fee_usd', 0))):
                    raise ValueError('Prepared transfer differs from approved amount, destination, or cost')
                plan['phase'] = 'transfer_submitting'
                if hasattr(self.backend, 'preflight'):
                    self.backend.preflight(buyer, 'transfers', transfer, plan)
                self.state.write(proposal_id, plan)
                self.backend.submit(buyer, 'transfers', transfer, guard)
                fill = self.backend.confirm(buyer, 'transfers', transfer['id'])
                fills.append(fill)
                if fill['status'] != 'completed' or not fill.get('tx_hash'):
                    raise ValueError('Transfer not confirmed on-chain')
                expected = dec(plan['pay_qty'])
                actual_fee = dec(fill['fee']) * dec(plan['target_price'])
                received = dec(fill['received'])
                sent = dec(fill['sent'])
                quality = {'expected_received': str(expected), 'actual_received': str(received),
                           'sent': str(sent), 'quoted_transfer_fee_usd': plan.get('transfer_fee_usd', '0'),
                           'actual_transfer_fee_usd': str(actual_fee),
                           'shortfall': str(max(Decimal(0), expected - received))}
                mismatch = (received < expected or sent != expected or
                            actual_fee > dec(plan.get('transfer_fee_usd', 0)))
                if mismatch:
                    quality['needs_reconciliation'] = True
                    self.state.hold({'proposal_id': proposal_id, 'tx_hash': fill['tx_hash'],
                                     'execution_quality': quality})
                receipt = {'quote': {'path': p['path'], 'expected_cost': p['expected_cost'],
                                     'swap': quote['raw'] if quote else None},
                           'fill': {'operations': fills, 'execution_quality': quality},
                           'tx_hash': fill['tx_hash'], 'status': 'failed' if mismatch else 'executed'}
            except Exception as e:
                # An error may occur after a chain submission. Save evidence, never retry blindly.
                receipt = {'quote': {'path': p['path'], 'expected_cost': p['expected_cost']},
                           'fill': {'error_type': type(e).__name__, 'phase': plan['phase'],
                                    'order': plan.get('order'), 'order_fill': plan.get('order_fill'),
                                    'transfer': plan.get('transfer'), 'needs_reconciliation': True},
                           'tx_hash': (plan.get('order_fill') or {}).get('tx_hash'), 'status': 'failed'}
            plan['receipt'], plan['phase'] = receipt, receipt['status']
            self.state.write(proposal_id, plan)
            if receipt['status'] == 'executed' and plan['mode'] == 'auto_top_up':
                # This creates pending proposals only; each buy-back needs its own
                # human decision. Never sign a second order under payment approval.
                followups = []
                for target in self.top_up_targets.get(buyer, []):
                    try:
                        pending = self.propose_top_up(buyer, target['asset_id'], target['weight'],
                            target['limit_price'], 'Restore target allocation after approved payment',
                            f'Payment receipt {proposal_id}; human-configured target allocation')
                        followups.append({'proposal_id': pending['id'], 'status': 'pending'})
                    except Exception as e:
                        followups.append({'status': 'not_proposed', 'reason_type': type(e).__name__})
                receipt['fill']['buy_back_proposals'] = followups
                plan['receipt'] = receipt
                self.state.write(proposal_id, plan)
            self.queue.receipt(proposal_id, receipt)
            return receipt

    def propose_top_up(self, buyer, asset_id, target_weight, limit_price, purpose, source):
        """A separate pending proposal, never an implicitly approved payment side effect."""
        if not purpose or not source:
            raise ValueError('Purpose and source are required for every order')
        catalog = {a['id']: a for a in self.backend.assets() if a.get('is_active')}
        target = catalog[asset_id]
        price = dec(limit_price)
        if price <= 0 or not target.get('tradeable') or target.get('type', 'spot') != 'spot':
            raise ValueError('An active spot asset and positive limit price are required')
        balances = self.backend.balances(buyer)
        values = {b['asset_id']: dec(b['available']) * dec(self.prices(catalog[b['asset_id']]))
                  for b in balances if b['asset_id'] in catalog}
        stable = next(catalog[b['asset_id']] for b in balances
                      if b['asset_id'] in catalog and catalog[b['asset_id']].get('stable')
                      and catalog[b['asset_id']].get('venue') == target.get('venue'))
        budget = min(self.max_payment, top_up_budget(sum(values.values()), values.get(asset_id, 0),
                                                    target_weight, values[stable['id']]))
        qty = (budget / price).quantize(Decimal(10) ** -target['decimals'], rounding=ROUND_DOWN)
        if qty <= 0:
            raise ValueError('Allocation is at target or no stablecoin is available')
        quote = self.backend.limit_preview(buyer, target, stable, qty, price)
        fee = dec(quote['fee']) * dec(self.prices(stable))
        if fee > self.max_fee or qty * price + fee > values[stable['id']]:
            raise ValueError('Limit order exceeds approved fee or stablecoin budget')
        gap = drift_bps(price, self.prices(target))
        if target.get('reference_symbol') and gap > self.max_drift:
            raise ValueError('Stock buy-back limit exceeds reference drift threshold')
        p = dict(id=str(uuid4()), buyer=buyer, seller=buyer, purpose=purpose,
                 amount_usd=float(qty * price),
                 path=[{'type': 'swap', 'asset': stable['symbol'], 'amount': str(qty * price)}],
                 expected_cost=float(fee), alternatives=[],
                 drift={'on_chain_price': float(price), 'reference_price': float(self.prices(target)),
                        'bps': float(gap)} if target.get('reference_symbol') else None,
                 flags=[f'LIMIT BUY {qty} {target["symbol"]} at no more than {price} {stable["symbol"]}',
                        'Separate buy-back approval required; order may rest unfilled',
                        'Stablecoin USD reference assumes $1'], source=source, status='pending')
        plan = dict(kind='top_up', proposal=p, fingerprint=fingerprint(p), created_at=time.time(),
                    phase='pending', target_asset=target, quantity=str(qty), limit_price=str(price),
                    quote=quote, stable=stable)
        self.state.write(p['id'], plan)
        result = self.queue.create(p)
        if result.get('status') != 'pending' or fingerprint(result) != plan['fingerprint']:
            raise ApprovalError('Queue altered or automatically approved the limit proposal')
        return result

    def propose_swap(self, buyer, source_id, target_id, amount_usd, min_output, purpose, source):
        amount, minimum = dec(amount_usd), dec(min_output)
        if not purpose or not source or not 0 < amount <= self.max_payment or minimum <= 0:
            raise ValueError('Valid swap amount, output floor, purpose and source required')
        catalog = {a['id']: a for a in self.backend.assets() if a.get('is_active')}
        src, target = catalog[source_id], catalog[target_id]
        if src['id'] == target['id']:
            raise ValueError('Swap must change assets')
        quantity = amount / dec(self.prices(src))
        available = next((dec(b['available']) for b in self.backend.balances(buyer)
                          if b['asset_id'] == source_id), Decimal(0))
        if quantity > available:
            raise ValueError('Insufficient funded source asset')
        maximum_cost = max(Decimal(0), amount - minimum * dec(self.prices(target)))
        if maximum_cost > self.max_fee or maximum_cost / amount * 10000 > self.max_impact:
            raise ValueError('Minimum swap output permits more loss than the configured cost limit')
        kind, prepared = self.backend.prepare_swap(buyer, src, target, quantity)
        plan = dict(kind='swap', source_asset=src, target_asset=target, input_qty=str(quantity),
                    pay_qty=str(minimum), recipient=None, submit_kind=kind,
                    created_at=time.time(), phase='pending')
        # Verify before approval too: the card reflects actual simulated economics.
        evidence = self.backend.preflight(buyer, kind, prepared, plan)
        p = dict(id=str(uuid4()), buyer=buyer, seller=buyer, purpose=purpose,
                 amount_usd=float(amount), path=[{'type':'swap','asset':src['symbol'],'amount':str(quantity)}],
                 expected_cost=float(maximum_cost), alternatives=[], drift=None,
                 flags=[f'STANDALONE SWAP: receive at least {minimum} {target["symbol"]} in the same wallet',
                        f'Spend at most {quantity} {src["symbol"]}; maximum reference-value cost ${maximum_cost}',
                        'Unsigned simulation passed; no seller transfer is included',
                        'Transfer execution remains held after the earlier fee discrepancy'],
                 source=source, status='pending')
        if getattr(self, 'swap_policy_note', None):
            p['flags'].append(self.swap_policy_note)
        plan.update(proposal=p, fingerprint=fingerprint(p), preflight={k:str(v) for k,v in evidence.items()})
        self.state.write(p['id'], plan)
        result = self.queue.create(p)
        if result['status'] != 'pending' or fingerprint(result) != plan['fingerprint']:
            raise ApprovalError('Queue changed or automatically approved the swap')
        return result

    def _execute_swap(self, ident, plan):
        if dry_run():
            return {'quote': {'dry_run':True, 'path':plan['proposal']['path'],
                              'minimum_output':plan['pay_qty']}, 'fill':None,
                    'tx_hash':None, 'status':'approved'}
        approval = self._approved(ident, plan)
        approved_at = (approval.get('decision') or {}).get('at', time.time())
        if plan['phase'] != 'pending' or time.time() - approved_at > 300:
            raise ValueError('Swap approval expired or execution already started; do not blindly retry')
        # The transfer hold stays in place. This isolated conversion has mandatory
        # independent simulation and a new, explicit human approval.
        buyer = plan['proposal']['buyer']
        kind, prepared = self.backend.prepare_swap(buyer, plan['source_asset'], plan['target_asset'],
                                                   dec(plan['input_qty']))
        self.backend.preflight(buyer, kind, prepared, plan)
        guard = lambda: self._approved(ident, plan)
        guard()
        plan['phase'], plan['prepared'] = 'swap_submitting', public(prepared)
        self.state.write(ident, plan)
        try:
            submitted = self.backend.submit(buyer, kind, prepared, guard)
            plan['submitted'] = public(submitted)
            self.state.write(ident, plan)
            if kind == 'trades' and submitted.get('tx_hash'):
                # Legacy DeFi order IDs are not necessarily Gateway-readable.
                # The chain audit below is authoritative confirmation.
                fill = {**public(submitted), 'status':'complete'}
            else:
                fill = self.backend.confirm(buyer, 'orders', submitted.get('order_id') or prepared['order_id'])
            plan['confirmed_fill'] = fill
            self.state.write(ident, plan)
            if fill.get('tx_hash') and hasattr(self.backend, 'audit_swap'):
                quality = self.backend.audit_swap(buyer, fill['tx_hash'], plan)
                fill['execution_quality'] = quality
                if not quality['matched_approved_bounds']:
                    self.state.hold({'proposal_id':ident,'tx_hash':fill['tx_hash'],'execution_quality':quality})
                    fill['status'] = 'failed'
            receipt = {'quote': {'maximum_input':plan['input_qty'], 'minimum_output':plan['pay_qty'],
                                  'prepared':public(prepared)}, 'fill':fill,
                       'tx_hash':fill.get('tx_hash'),
                       'status':'executed' if fill['status'] == 'complete' and fill.get('tx_hash') else 'failed'}
        except Exception as e:
            receipt = {'quote':public(prepared), 'fill':{'error_type':type(e).__name__,
                       'needs_reconciliation':True, 'submitted':plan.get('submitted')},
                       'tx_hash':(plan.get('confirmed_fill') or plan.get('submitted') or {}).get('tx_hash'), 'status':'failed'}
        plan['receipt'], plan['phase'] = receipt, receipt['status']
        self.state.write(ident, plan)
        self.queue.receipt(ident, receipt)
        return receipt

    def _execute_top_up(self, ident, plan):
        p = plan['proposal']
        if dry_run():
            return {'quote': {'dry_run': True, 'limit_price': plan['limit_price'],
                              'quantity': plan['quantity'], 'asset': plan['target_asset']['symbol']},
                    'fill': None, 'tx_hash': None, 'status': 'approved'}
        self.state.check_hold()
        if plan['phase'] == 'pending':
            if time.time() - plan['created_at'] > 300:
                raise ValueError('Limit proposal expired; propose again')
            fresh = self.backend.limit_preview(p['buyer'], plan['target_asset'], plan['stable'],
                                               dec(plan['quantity']), dec(plan['limit_price']))
            if dec(fresh['fee']) > dec(plan['quote']['fee']):
                raise ValueError('Limit fees increased; fresh human approval required')
            self._approved(ident, plan)
            plan['phase'] = 'limit_submitting'
            self.state.write(ident, plan)
            # CeFi creation can immediately execute. No retry on ambiguous response.
            created = self.backend.create_limit(p['buyer'], plan['target_asset'],
                                                plan['quantity'], plan['limit_price'])
            plan['order'] = public(created)
            self.state.write(ident, plan)
            if created.get('payloads'):
                self.backend.submit(p['buyer'], 'orders', created, lambda: self._approved(ident, plan))
            plan['phase'] = 'limit_active'
            self.state.write(ident, plan)
        if plan['phase'] != 'limit_active':
            raise RuntimeError('Limit submission uncertain; reconcile without resubmission')
        fill = self.backend.read_order(p['buyer'], plan['order']['order_id'])
        receipt = {'quote': {'limit_price': plan['limit_price'], 'quantity': plan['quantity'],
                              'preview': plan['quote']}, 'fill': fill,
                   'tx_hash': fill.get('tx_hash'), 'status': 'approved'}
        if fill['status'] in {'complete', 'failed', 'canceled'}:
            receipt['status'] = 'executed' if fill['status'] == 'complete' else 'failed'
            plan['receipt'], plan['phase'] = receipt, receipt['status']
            self.state.write(ident, plan)
            self.queue.receipt(ident, receipt)
        return receipt

    def plan_top_up(self, total_usd, current_value_usd, target_weight, stable_available_usd, limit_price):
        budget = top_up_budget(total_usd, current_value_usd, target_weight, stable_available_usd)
        price = dec(limit_price)
        if price <= 0:
            raise ValueError('Positive limit price required')
        return {'budget_usd': str(budget), 'quantity': str(budget / price),
                'limit_price': str(price), 'requires_separate_human_approval': True,
                'executable': False}

    def create_wallet(self, name):
        return self.backend.create_wallet(name)

    def propose_funding(self, buyer, escrow, amount_usd, purpose, source):
        return self.propose_payment(buyer, escrow, amount_usd, purpose, source)

    def propose_payout(self, escrow, worker, amount_usd, purpose, source):
        return self.propose_payment(escrow, worker, amount_usd, purpose, source)

    def propose_refund(self, escrow, poster, amount_usd, purpose, source):
        return self.propose_payment(escrow, poster, amount_usd, purpose, source)


def build_router():
    path = os.getenv('RUNWAY_ACCOUNTS_FILE', '.runway/accounts.json')
    with open(path) as f:
        config = json.load(f)
    return PaymentRouter(TrueMarketsBackend(signer_files=config['signer_files'],
                                             asset_metadata=config.get('asset_metadata')),
                         HTTPQueue(os.getenv('RUNWAY_QUEUE_URL', 'http://localhost:8000'), strict_live=True),
                         config['sellers'], modes=config.get('modes'),
                         top_up_targets=config.get('top_up_targets'),
                         max_payment_usd=os.getenv('RUNWAY_MAX_PAYMENT_USD', '1'),
                         max_impact_bps=os.getenv('RUNWAY_MAX_IMPACT_BPS', '100'),
                         max_drift_bps=os.getenv('RUNWAY_MAX_DRIFT_BPS', '200'))
