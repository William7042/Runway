"""Private local buyer capabilities; never place them in public queue responses."""
import json
import os
from pathlib import Path
import re

ROOT=Path('.runway/buyer-jobs')


def path(job_id):
    if not re.fullmatch(r'job-[0-9a-f]{16}',job_id):raise ValueError('Invalid job ID')
    return ROOT/(job_id+'.json')


def save(job):
    if not job.get('buyer_token'):return
    target=path(job['id']);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump({'job_id':job['id'],'buyer_token':job['buyer_token']},f)


def token(job_id):
    target=path(job_id)
    return json.loads(target.read_text())['buyer_token'] if target.exists() else ''
