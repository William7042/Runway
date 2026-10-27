import base64
from pathlib import Path
import pytest
from test_product_integration import integrated
from test_marketplace import register, job, bind, pay


def uploaded(c,j,s,name='report.pdf',content=b'%PDF demo',mime='application/pdf'):
    return c.post('/specialist-jobs/'+j['id']+'/artifacts',json={'owner_token':s['owner_token'],
        'filename':name,'mime_type':mime,'description':'Review report','content_base64':base64.b64encode(content).decode()})


def test_private_multifile_delivery_requires_paid_job_and_buyer_capability(integrated,monkeypatch,tmp_path):
    _,_,c=integrated
    import artifacts
    monkeypatch.setattr(artifacts,'ROOT',tmp_path/'files')
    s=register(c);j=job(c,s);token=j['buyer_token'];p,_=bind(c,j)
    assert 'buyer_token_hash' not in str(c.get('/specialist-jobs/'+j['id']).json())
    assert 'buyer_token' not in job(c,s) # idempotent public retry never reveals capability
    assert uploaded(c,j,s).status_code==409
    pay(c,p)
    pdf=uploaded(c,j,s);assert pdf.status_code==201
    csv=uploaded(c,j,s,'data.csv',b'a,b\n1,2','text/csv');assert csv.status_code==201
    assert uploaded(c,j,s).json()['id']==pdf.json()['id']
    endpoint='/specialist-jobs/'+j['id']+'/delivery'
    assert c.post(endpoint,json={'buyer_token':token}).status_code==409
    c.post('/specialist-jobs/'+j['id']+'/result',json={'owner_token':s['owner_token'],'result':''}).raise_for_status()
    public=c.get('/specialist-jobs/'+j['id']).json();assert public['artifact_count']==2 and 'artifacts' not in public
    assert c.post(endpoint,json={}).status_code==403
    assert c.post(endpoint,json={'buyer_token':'wrong'}).status_code==403
    delivered=c.post(endpoint,json={'buyer_token':token});assert len(delivered.json()['artifacts'])==2
    path='/specialist-jobs/'+j['id']+'/artifacts/'+pdf.json()['id']+'/download'
    assert c.post(path,json={}).status_code==403
    result=c.post(path,json={'buyer_token':token});assert result.content==b'%PDF demo'
    assert result.headers['x-content-type-options']=='nosniff'
    assert result.headers['content-disposition'].startswith('attachment;')
    assert uploaded(c,j,s,'late.txt').status_code==409
    assert all(f.stat().st_mode&0o777==0o600 for f in (tmp_path/'files').iterdir())


def test_files_reject_traversal_invalid_encoding_wrong_owner_and_limits(integrated,monkeypatch,tmp_path):
    _,_,c=integrated
    import artifacts
    monkeypatch.setattr(artifacts,'ROOT',tmp_path/'files')
    s=register(c);j=job(c,s);p,_=bind(c,j);pay(c,p)
    assert uploaded(c,j,s,'../secret').status_code==422
    assert uploaded(c,j,{**s,'owner_token':'wrong'}).status_code==403
    body={'owner_token':s['owner_token'],'filename':'x.txt','content_base64':'invalid!'}
    assert c.post('/specialist-jobs/'+j['id']+'/artifacts',json=body).status_code==422
    for i in range(5):assert uploaded(c,j,s,f'{i}.txt',str(i).encode(),'text/plain').status_code==201
    assert uploaded(c,j,s,'six.txt',b'6','text/plain').status_code==413


def test_other_buyer_token_cannot_download_and_legacy_jobs_have_no_implicit_access(integrated,monkeypatch,tmp_path):
    _,_,c=integrated
    import artifacts
    monkeypatch.setattr(artifacts,'ROOT',tmp_path/'files')
    s=register(c);j=job(c,s);other=job(c,s,'another-job-1234');p,_=bind(c,j);pay(c,p)
    file=uploaded(c,j,s).json()
    c.post('/specialist-jobs/'+j['id']+'/result',json={'owner_token':s['owner_token'],'result':'Done'})
    path='/specialist-jobs/'+j['id']+'/artifacts/'+file['id']+'/download'
    assert c.post(path,json={'buyer_token':other['buyer_token']}).status_code==403


def test_file_size_total_and_symlink_limits(integrated,monkeypatch,tmp_path):
    _,_,c=integrated
    import artifacts
    monkeypatch.setattr(artifacts,'ROOT',tmp_path/'files')
    monkeypatch.setattr(artifacts,'MAX_FILE',5)
    monkeypatch.setattr(artifacts,'MAX_TOTAL',5)
    s=register(c);j=job(c,s);p,_=bind(c,j);pay(c,p)
    assert uploaded(c,j,s,'large.txt',b'123456','text/plain').status_code==413
    assert uploaded(c,j,s,'empty.txt',b'','text/plain').status_code==413
    f=uploaded(c,j,s,'ok.txt',b'1234','text/plain').json()
    assert uploaded(c,j,s,'over-total.txt',b'12','text/plain').status_code==413
    c.post('/specialist-jobs/'+j['id']+'/result',json={'owner_token':s['owner_token'],'result':'Complete'})
    stored=tmp_path/'files'/f['id'];stored.unlink()
    outside=tmp_path/'private.txt';outside.write_bytes(b'secret');stored.symlink_to(outside)
    path='/specialist-jobs/'+j['id']+'/artifacts/'+f['id']+'/download'
    assert c.post(path,json={'buyer_token':j['buyer_token']}).status_code==404


def test_legacy_job_without_capability_cannot_gain_access(integrated,monkeypatch,tmp_path):
    _,_,c=integrated
    import sys
    s=register(c);j=job(c,s);p,_=bind(c,j);pay(c,p)
    c.post('/specialist-jobs/'+j['id']+'/result',json={'owner_token':s['owner_token'],'result':'Complete'})
    with sys.modules['test_product_queue'].Store() as store:
        next(x for x in store['specialist_jobs'] if x['id']==j['id']).pop('buyer_token_hash')
    assert c.post('/specialist-jobs/'+j['id']+'/delivery',json={'buyer_token':j['buyer_token']}).status_code==403


def test_empty_oversize_and_total_delivery_limit(integrated,monkeypatch,tmp_path):
    _,_,c=integrated
    import artifacts
    monkeypatch.setattr(artifacts,'ROOT',tmp_path/'files')
    monkeypatch.setattr(artifacts,'MAX_FILE',8)
    monkeypatch.setattr(artifacts,'MAX_TOTAL',12)
    s=register(c);j=job(c,s);p,_=bind(c,j);pay(c,p)
    assert uploaded(c,j,s,'empty.txt',b'','text/plain').status_code==413
    assert uploaded(c,j,s,'large.txt',b'123456789','text/plain').status_code==413
    assert uploaded(c,j,s,'first.txt',b'12345678','text/plain').status_code==201
    assert uploaded(c,j,s,'second.txt',b'12345','text/plain').status_code==413
    assert len(list((tmp_path/'files').iterdir()))==1
