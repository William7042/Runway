import hashlib
import json
from decimal import Decimal
import httpx
import pytest
from runway_money.preflight import SolanaPreflight, b58


def fixture(result):
    owner = b58(bytes([7])*32)
    recipient = b58(bytes([8])*32)
    # Valid transaction header layout; the RPC response is injected, never broadcast.
    raw = b'\x01' + bytes(64) + b'\x01\x00\x00\x02' + bytes([7])*32 + bytes([8])*32 + bytes(32) + b'\x00'
    activity = {'type':'ACTIVITY_TYPE_SIGN_TRANSACTION_V2','parameters':{
        'type':'TRANSACTION_TYPE_SOLANA','signWith':owner,'unsignedTransaction':raw.hex()}}
    payload = json.dumps(activity)
    prepared = {'payloads':[{'payload':payload,'digest':hashlib.sha256(payload.encode()).hexdigest()}]}
    client = httpx.Client(transport=httpx.MockTransport(lambda request:
        httpx.Response(200,json={'result':{'value':result}})))
    return SolanaPreflight(client=client), prepared, owner, recipient


def balance(owner, mint, amount):
    return {'owner':owner,'mint':mint,'uiTokenAmount':{'amount':str(amount),'decimals':6}}


def test_simulated_hidden_fee_stops_before_signing():
    owner, target = b58(bytes([7])*32), b58(bytes([8])*32)
    result = {'err':None,'fee':10000,'preBalances':[1,1],'postBalances':[1,1],
              'preTokenBalances':[balance(owner,'mint',10000000),balance(target,'mint',0)],
              'postTokenBalances':[balance(owner,'mint',5000000),balance(target,'mint',4000000)]}
    guard, prepared, owner, target = fixture(result)
    asset = {'address':'mint','symbol':'PYUSD','chain':'solana'}
    with pytest.raises(ValueError,match='recipient'):
        guard.verify(prepared,owner,input_asset=asset,output_asset=asset,
                     max_input=5,min_output=5,recipient=target)


def test_simulated_swap_checks_all_wallet_debits_and_net_output():
    owner = b58(bytes([7])*32)
    result = {'err':None,'fee':10000,'preBalances':[1,1],'postBalances':[1,1],
              'preTokenBalances':[balance(owner,'pyusd',10000000),balance(owner,'usdc',0)],
              'postTokenBalances':[balance(owner,'pyusd',8000000),balance(owner,'usdc',1995000)]}
    guard, prepared, owner, _ = fixture(result)
    a={'address':'pyusd','symbol':'PYUSD','chain':'solana'}
    b={'address':'usdc','symbol':'USDC','chain':'solana'}
    assert guard.verify(prepared,owner,input_asset=a,output_asset=b,max_input=2,min_output='1.99')['token_deltas']['usdc'] == Decimal('1.995')
    result['postTokenBalances'].append(balance(owner,'unapproved',0))
    result['preTokenBalances'].append(balance(owner,'unapproved',1000000))
    with pytest.raises(ValueError,match='unapproved token'):
        guard.verify(prepared,owner,input_asset=a,output_asset=b,max_input=2,min_output='1.99')


def test_multitransaction_bridge_is_rejected_without_rpc_or_signing():
    guard, prepared, owner, _ = fixture({})
    prepared['payloads'] *= 2
    with pytest.raises(ValueError,match='bridge'):
        guard.inspect(prepared,owner)


def test_transfer_preview_uses_simulated_fee_not_zero_pending_api_fields(monkeypatch):
    from runway_money.backend import TrueMarketsBackend
    owner, recipient = 'buyer-wallet', 'seller-wallet'
    simulation = {'preTokenBalances':[balance(owner,'mint',10000000), balance(recipient,'mint',0)],
                  'postTokenBalances':[balance(owner,'mint',5000000),balance(recipient,'mint',4000000)]}
    monkeypatch.setattr(SolanaPreflight,'inspect',lambda *args:{
        'token_deltas':{'mint':Decimal('-5')}, 'native_delta':Decimal(0), '_simulation':simulation})
    backend = TrueMarketsBackend(client=object())
    backend.assets = lambda:[{'id':'asset','address':'mint','chain':'solana','symbol':'PYUSD'}]
    backend.user = lambda name:{'wallets':[{'chain_family':'solana','address':owner}]}
    backend.prepare_transfer = lambda *args:{'asset_id':'asset','to':recipient,'fee':'0','received':'0',
                                            'status':'awaiting_signature','payloads':[]}
    preview = backend.preview_transfer('buyer','asset','5',recipient)
    assert preview['api_reported_fee'] == '0' and preview['api_reported_received'] == '0'
    assert preview['fee'] == '1' and preview['received'] == '4' and preview['sent'] == '5'
    assert preview['fee_source'] == 'unsigned_solana_simulation'
    assert 'payloads' not in preview
