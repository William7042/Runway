import json
import stat
import pytest
from test_product_integration import integrated


def profile(client):
    return client.post('/specialists',json={'name':'Demo reviewer','capability':'Review payment flows',
        'price_usd':4,'accepts':['PYUSD'],'payout_user':'test2'}).json()


def test_registration_saves_private_latest_and_per_listing_copy(integrated,monkeypatch,tmp_path):
    _,_,c=integrated
    import marketplace
    monkeypatch.setenv('RUNWAY_DEMO_SELLER_AUTOSAVE','1')
    monkeypatch.setattr(marketplace,'DEMO_ROOT',tmp_path/'private-demo')
    result=profile(c)
    assert result['credentials_saved'] is True
    root=marketplace.DEMO_ROOT
    for p in [root/'demo-seller.json',root/'seller-credentials'/(result['id']+'.json')]:
        saved=json.loads(p.read_text())
        assert saved['specialist_id']==result['id'] and saved['owner_token']==result['owner_token']
        assert stat.S_IMODE(p.stat().st_mode)==0o600
    assert result['owner_token'] not in c.get('/specialists').text
    assert 'owner_token_hash' not in c.get('/specialists').text


def test_existing_browser_owner_can_save_but_wrong_token_cannot(integrated,monkeypatch,tmp_path):
    _,_,c=integrated
    import marketplace
    monkeypatch.setattr(marketplace,'DEMO_ROOT',tmp_path/'private-demo')
    monkeypatch.delenv('RUNWAY_DEMO_SELLER_AUTOSAVE',raising=False)
    result=profile(c)
    assert result['credentials_saved'] is False
    assert not marketplace.DEMO_ROOT.exists()
    url=f'/specialists/{result["id"]}/demo-credentials'
    assert c.post(url,json={'owner_token':result['owner_token']}).status_code==403
    monkeypatch.setenv('RUNWAY_DEMO_SELLER_AUTOSAVE','1')
    assert c.post(url,json={'owner_token':'wrong'}).status_code==403
    assert not marketplace.DEMO_ROOT.exists()
    assert c.post(url,json={'owner_token':result['owner_token']}).json()['credentials_saved'] is True


def test_new_listing_does_not_erase_other_listing_credentials(integrated,monkeypatch,tmp_path):
    _,_,c=integrated
    import marketplace
    monkeypatch.setenv('RUNWAY_DEMO_SELLER_AUTOSAVE','1')
    monkeypatch.setattr(marketplace,'DEMO_ROOT',tmp_path/'private-demo')
    one=profile(c);two=profile(c)
    assert json.loads((marketplace.DEMO_ROOT/'demo-seller.json').read_text())['specialist_id']==two['id']
    assert (marketplace.DEMO_ROOT/'seller-credentials'/(one['id']+'.json')).exists()
