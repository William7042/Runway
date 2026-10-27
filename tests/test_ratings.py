import sys
import pytest
from test_product_integration import integrated
from test_marketplace import register, job, bind, pay


def delivered(c):
    seller=register(c);j=job(c,seller);p,_=bind(c,j)
    pay(c,p)
    c.post('/specialist-jobs/'+j['id']+'/result',json={'owner_token':seller['owner_token'],'result':'Delivered'}).raise_for_status()
    return seller,j,p


def rate(c,j,**patch):
    return c.post('/specialist-jobs/'+j['id']+'/rating',json={
        'buyer_token':j['buyer_token'],'stars':5,'review':'Useful work',**patch})


def test_verified_review_persists_aggregates_and_is_one_per_job(integrated):
    _,_,c=integrated;s,j,_=delivered(c)
    assert rate(c,j).status_code==200
    assert rate(c,j).status_code==200
    assert rate(c,j,stars=4).status_code==409
    profile=next(x for x in c.get('/specialists').json() if x['id']==s['id'])
    assert profile['rating_average']==5 and profile['rating_count']==1
    reviews=c.get('/specialists/'+s['id']+'/reviews').json()
    assert len(reviews)==1 and reviews[0]['verified_purchase'] is True
    assert j['buyer_token'] not in str(reviews)


def test_seller_and_unauthorized_buyer_cannot_rate(integrated):
    _,_,c=integrated;s,j,_=delivered(c)
    assert rate(c,j,buyer_token='wrong').status_code==403
    assert rate(c,j,buyer_token=s['owner_token']).status_code==403


@pytest.mark.parametrize('change',['unpaid','incomplete','simulated','self_purchase','shortfall'])
def test_invalid_purchases_do_not_receive_verified_ratings(integrated,change):
    _,_,c=integrated;_,j,p=delivered(c)
    with sys.modules['test_product_queue'].Store() as s:
        item=next(x for x in s['specialist_jobs'] if x['id']==j['id'])
        proposal=next(x for x in s['proposals'] if x['id']==p['id'])
        if change=='unpaid':proposal['status']='approved'
        elif change=='incomplete':item['status']='paid'
        elif change=='simulated':item['simulated']=True
        elif change=='self_purchase':item['buyer']=item['seller']
        else:proposal['receipt']['fill']['execution_quality']['shortfall']='0.1'
    assert rate(c,j).status_code==409


@pytest.mark.parametrize('stars',[0,6,1.5,True,'5'])
def test_invalid_star_values(integrated,stars):
    _,_,c=integrated;_,j,_=delivered(c)
    assert rate(c,j,stars=stars).status_code==422
