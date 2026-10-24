"""Local marketplace extensions. Money remains in the approval-guarded router."""
import hashlib
import secrets
import time
import uuid
from decimal import Decimal
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

TOKENS={'USDC','PYUSD','SOL','BTC','ETH'}


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _public(profile):
    return {k:v for k,v in profile.items() if k not in {'owner_token_hash','base'}}


class Listing(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=2,max_length=100)
    capability: str = Field(min_length=8,max_length=2000)
    price_usd: float = Field(gt=0,le=5,allow_inf_nan=False)
    accepts: list[str] = Field(min_length=1,max_length=5)
    payout_user: str = Field(min_length=1,max_length=100)
    endpoint: str = ''
    simulated: bool = False

    @field_validator('accepts')
    @classmethod
    def accepted(cls,value):
        if any(v not in TOKENS for v in value): raise ValueError('Unsupported commerce token')
        return sorted(set(value))

    @field_validator('endpoint')
    @classmethod
    def endpoint_url(cls,value):
        if value:
            p=urlsplit(value)
            if p.scheme!='https' or not p.hostname or p.username or p.password:
                raise ValueError('Endpoint must be HTTPS without credentials')
        return value


class Update(BaseModel):
    owner_token: str
    price_usd: float | None = Field(default=None,gt=0,le=5,allow_inf_nan=False)
    capability: str | None = Field(default=None,min_length=8,max_length=2000)
    active: bool | None = None


class JobRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    specialist_id: str
    buyer: str = Field(min_length=1,max_length=100)
    request: str = Field(min_length=8,max_length=10000)
    idempotency_key: str = Field(min_length=8,max_length=100)


class Payment(BaseModel):
    proposal_id: str


class Result(BaseModel):
    owner_token: str
    result: str = Field(min_length=1,max_length=50000)


def install(app, Store, find):
    router=APIRouter()
    def listing(s, ident):
        return find(s.get('registered_specialists',[]),ident,'specialist')
    def owner(profile, token):
        if not secrets.compare_digest(profile['owner_token_hash'],_hash(token)):
            raise HTTPException(403,'Invalid seller owner token')
    def paid(s,job):
        if not job.get('proposal_id'): return False
        p=find(s['proposals'],job['proposal_id'],'proposal')
        receipt=p.get('receipt') or {}
        if p['status']!='executed' or receipt.get('status')!='executed': return False
        if job['simulated']:
            return bool((receipt.get('quote') or {}).get('simulated') or (receipt.get('fill') or {}).get('simulated'))
        quality=(receipt.get('fill') or {}).get('execution_quality') or {}
        expected=Decimal(str(quality.get('expected_received',0)))
        actual=Decimal(str(quality.get('actual_received',0)))
        return bool(receipt.get('tx_hash') and expected>0 and actual>=expected
                    and not quality.get('needs_reconciliation')
                    and Decimal(str(quality.get('shortfall',0)))==0)
    def job_view(s,job):
        result=dict(job)
        if job['status']!='complete':
            result['status']='paid' if paid(s,job) else 'awaiting_payment'
            if job.get('proposal_id'):
                p=find(s['proposals'],job['proposal_id'],'proposal')
                if p['status'] in {'rejected','failed'}: result['status']=p['status']
        return result

    @router.post('/specialists',status_code=201)
    def register(body: Listing):
        token=secrets.token_urlsafe(32)
        with Store() as s:
            profile={**body.model_dump(),'id':'specialist-'+uuid.uuid4().hex[:12],
                'active':True,'owner_token_hash':_hash(token),'created_at':time.time(),
                'private_asset':'Vendor-provided specialist work','unit':'per job',
                'base':{'jobs':0,'earned_usd':0,'refunds':0}}
            s.setdefault('registered_specialists',[]).append(profile)
            return {**_public(profile),'owner_token':token,
                    'note':'Keep owner_token private. Listing does not verify wallet ownership or enable a payment route.'}

    @router.get('/specialists/{ident}')
    def get_listing(ident: str):
        with Store() as s: return _public(listing(s,ident))

    @router.patch('/specialists/{ident}')
    def update(ident: str,body: Update):
        with Store() as s:
            profile=listing(s,ident);owner(profile,body.owner_token)
            profile.update(body.model_dump(exclude={'owner_token'},exclude_none=True))
            return _public(profile)

    @router.post('/specialist-jobs',status_code=201)
    def request_job(body: JobRequest):
        with Store() as s:
            profile=listing(s,body.specialist_id)
            if not profile['active']: raise HTTPException(409,'Specialist is inactive')
            for old in s.get('specialist_jobs',[]):
                if old['buyer']==body.buyer and old['idempotency_key']==body.idempotency_key:
                    if old['specialist_id']!=body.specialist_id or old['request']!=body.request:
                        raise HTTPException(409,'Idempotency key belongs to another request')
                    return job_view(s,old)
            job={**body.model_dump(),'id':'job-'+uuid.uuid4().hex[:16],
                'seller':profile['payout_user'],'price_usd':profile['price_usd'],
                'accepts':list(profile['accepts']),'simulated':profile['simulated'],
                'status':'awaiting_payment','proposal_id':None,'result':None,'created_at':time.time()}
            s.setdefault('specialist_jobs',[]).append(job)
            return job

    @router.get('/specialist-jobs/{ident}')
    def get_job(ident: str):
        with Store() as s: return job_view(s,find(s.get('specialist_jobs',[]),ident,'job'))

    @router.post('/specialist-jobs/{ident}/payment')
    def bind_payment(ident: str,body: Payment):
        with Store() as s:
            job=find(s.get('specialist_jobs',[]),ident,'job')
            if job.get('proposal_id'):
                if job['proposal_id']!=body.proposal_id: raise HTTPException(409,'Job already has a payment proposal')
                return job_view(s,job)
            if any(j.get('proposal_id')==body.proposal_id for j in s.get('specialist_jobs',[])):
                raise HTTPException(409,'Payment already belongs to another job')
            p=find(s['proposals'],body.proposal_id,'proposal')
            source=p.get('source');source=source.get('text') if isinstance(source,dict) else source
            transfers=[step for step in p.get('path',[]) if step['type']=='transfer']
            if (p['buyer']!=job['buyer'] or p['seller']!=job['seller']
                or Decimal(str(p['amount_usd']))!=Decimal(str(job['price_usd']))
                or source!='user:specialist-job:'+ident or len(transfers)!=1
                or transfers[0]['asset'] not in job['accepts']):
                raise HTTPException(409,'Payment does not match this job invoice, recipient, or source')
            if not job['simulated'] and any('SIMULATED' in str(f).upper() for f in p.get('flags',[])):
                raise HTTPException(409,'A simulated payment cannot purchase a live service')
            job['proposal_id']=body.proposal_id
            return job_view(s,job)

    @router.post('/specialists/{ident}/jobs')
    def seller_jobs(ident: str,body: Update):
        with Store() as s:
            owner(listing(s,ident),body.owner_token)
            # Unpaid requests never start paid work. They remain visible to buyers.
            return [job_view(s,j) for j in s.get('specialist_jobs',[])
                    if j['specialist_id']==ident and paid(s,j)]

    @router.post('/specialist-jobs/{ident}/result')
    def submit_result(ident: str,body: Result):
        with Store() as s:
            job=find(s.get('specialist_jobs',[]),ident,'job')
            owner(listing(s,job['specialist_id']),body.owner_token)
            if not paid(s,job): raise HTTPException(409,'Confirmed full payment is required before delivery')
            if job['status']=='complete':
                if job['result']!=body.result: raise HTTPException(409,'Result already submitted')
                return job_view(s,job)
            job.update(status='complete',result=body.result,completed_at=time.time())
            return job_view(s,job)

    app.include_router(router)
