"""One buyer-authenticated review per completed, genuinely paid specialist job."""
import time
from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class RatingIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    buyer_token: str = Field(min_length=1, max_length=300)
    stars: int = Field(ge=1, le=5, strict=True)
    review: str = Field(default='', max_length=2000)


def verified_paid(store, job):
    proposal = next((p for p in store['proposals'] if p['id'] == job.get('proposal_id')), {})
    receipt = proposal.get('receipt') or {}
    quality = (receipt.get('fill') or {}).get('execution_quality') or {}
    tx = receipt.get('tx_hash') or ''
    expected = Decimal(str(quality.get('expected_received', 0)))
    return bool(not job.get('simulated') and job['buyer'] != job['seller']
                and proposal.get('status') == receipt.get('status') == 'executed'
                and proposal.get('buyer') == job['buyer'] and proposal.get('seller') == job['seller']
                and Decimal(str(proposal.get('amount_usd', 0))) == Decimal(str(job['price_usd']))
                and tx and not tx.upper().startswith(('STUB', 'SIMULATED'))
                and not (receipt.get('quote') or {}).get('simulated')
                and not (receipt.get('fill') or {}).get('simulated')
                and expected > 0 and Decimal(str(quality.get('actual_received', 0))) >= expected
                and Decimal(str(quality.get('shortfall', 0))) == 0
                and not quality.get('needs_reconciliation'))


def eligible_reviews(store, specialist_id):
    jobs = {j['id']: j for j in store.get('specialist_jobs', [])}
    return [r for r in store.get('specialist_ratings', [])
            if r['specialist_id'] == specialist_id and r['job_id'] in jobs
            and jobs[r['job_id']]['status'] == 'complete' and verified_paid(store, jobs[r['job_id']])]


def rating_summary(store, specialist_id):
    reviews = eligible_reviews(store, specialist_id)
    return {'rating_average': round(sum(r['stars'] for r in reviews) / len(reviews), 2) if reviews else None,
            'rating_count': len(reviews)}


def install(app, Store, find):
    router = APIRouter()

    @router.post('/specialist-jobs/{ident}/rating')
    def rate(ident: str, body: RatingIn):
        from marketplace import authorize_buyer
        with Store() as store:
            job = find(store.get('specialist_jobs', []), ident, 'job')
            authorize_buyer(job, body.buyer_token)
            if job['status'] != 'complete' or not verified_paid(store, job):
                raise HTTPException(409, 'Ratings require a completed real paid job between different buyers and sellers')
            ratings = store.setdefault('specialist_ratings', [])
            old = next((r for r in ratings if r['job_id'] == ident), None)
            if old:
                if old['stars'] == body.stars and old['review'] == body.review:
                    return old
                raise HTTPException(409, 'This job has already been rated')
            rating = {'job_id': ident, 'specialist_id': job['specialist_id'],
                      'buyer': job['buyer'], 'stars': body.stars, 'review': body.review,
                      'verified_purchase': True, 'created_at': time.time()}
            ratings.append(rating)
            return rating

    @router.get('/specialists/{ident}/reviews')
    def reviews(ident: str):
        with Store() as store:
            find(store.get('registered_specialists', []), ident, 'specialist')
            return sorted(eligible_reviews(store, ident), key=lambda r: r['created_at'], reverse=True)

    app.include_router(router)
