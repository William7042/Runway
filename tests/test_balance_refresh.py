import asyncio
import json
import pytest
from runway_money.balances import snapshot, sync, watch


class ReadOnlyBackend:
    def __init__(self): self.amount=43;self.fail=False;self.calls=[]
    def balances(self,user):
        self.calls.append(user)
        if self.fail and user=='test2': raise RuntimeError('Do not expose request secret')
        return [{'symbol':'PYUSD','available':str(self.amount),'stable':True,'chain':'solana','asset_id':'pyusd'},
                {'symbol':'SOL','available':'.01','stable':False,'chain':'solana','asset_id':'sol'}]


def test_snapshot_uses_api_amounts_and_keeps_unpriced_assets_unknown():
    b=ReadOnlyBackend();result=snapshot(b,'test')
    assert result['assets'][0]['amount']==43
    assert result['assets'][1]['usd_value'] is None
    assert result['simulated'] is False and result['snapshot_at']


def test_refresh_replaces_stale_snapshot_and_preserves_failed_wallet():
    b=ReadOnlyBackend();b.amount=38;b.fail=True
    saved={'test':{'amount':43},'test2':{'amount':4}}
    errors=sync(b,lambda user,value:saved.update({user:value}),{'signer_files':{'test':'ignored','test2':'ignored'}})
    assert saved['test']['assets'][0]['amount']==38
    assert saved['test2']=={'amount':4}
    assert errors=={'test2':'RuntimeError'}
    assert 'secret' not in str(errors)


def test_polling_repeats_without_overlapping_or_submitting(tmp_path,monkeypatch):
    path=tmp_path/'accounts.json';path.write_text(json.dumps({'signer_files':{'test':'ignored'}}))
    b=ReadOnlyBackend();snapshots=[];sleeps=[]
    async def sleep(seconds):
        sleeps.append(seconds)
        b.amount=38
        if len(sleeps)==2: raise asyncio.CancelledError
    monkeypatch.setattr('runway_money.balances.asyncio.sleep',sleep)
    async def run():
        with pytest.raises(asyncio.CancelledError):
            await watch(lambda user,value:snapshots.append(value),interval=5,
                        backend_factory=lambda:b,accounts_path=path)
    asyncio.run(run())
    assert [s['assets'][0]['amount'] for s in snapshots]==[43,38]
    assert len(b.calls)==2
    assert all(0<duration<=5 for duration in sleeps)
