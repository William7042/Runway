"""Private file delivery storage. Capability checks live in marketplace routes."""
import base64
import binascii
import hashlib
import os
from pathlib import Path
import re
import uuid
from fastapi import HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2] / '.runway' / 'artifacts'
MAX_FILE = 10 * 1024 * 1024
MAX_TOTAL = 25 * 1024 * 1024
MAX_FILES = 5


class ArtifactUpload(BaseModel):
    owner_token: str
    filename: str = Field(min_length=1, max_length=180)
    mime_type: str = Field(default='application/octet-stream', max_length=120)
    description: str = Field(default='', max_length=1000)
    content_base64: str = Field(max_length=((MAX_FILE + 2) // 3) * 4)


class ArtifactAccess(BaseModel):
    buyer_token: str = ''
    owner_token: str = ''


def upload(job, body):
    if '/' in body.filename or '\\' in body.filename or any(ord(c)<32 for c in body.filename) or body.filename in {'.','..'}:
        raise HTTPException(422, 'Use a filename without folders or control characters')
    if not re.fullmatch(r'[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+', body.mime_type):
        raise HTTPException(422, 'Invalid MIME type')
    existing = job.get('artifacts', [])
    try:
        data = base64.b64decode(body.content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, 'Invalid base64 file content')
    if not data or len(data)>MAX_FILE:
        raise HTTPException(413, 'Files must contain 1 byte to 10 MiB')
    digest=hashlib.sha256(data).hexdigest()
    for old in existing:
        if old['filename']==body.filename and old['sha256']==digest and old['description']==body.description and old['mime_type']==body.mime_type:
            return old
    if len(existing)>=MAX_FILES or sum(a['size_bytes'] for a in existing)+len(data)>MAX_TOTAL:
        raise HTTPException(413, 'Delivery limit: five files and 25 MiB total')
    ident='artifact-'+uuid.uuid4().hex
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(ROOT,0o700)
    fd=os.open(ROOT/ident,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(data)
    record={'id':ident,'filename':body.filename,'mime_type':body.mime_type,
            'size_bytes':len(data),'description':body.description,'sha256':digest}
    job.setdefault('artifacts',[]).append(record)
    return record


def file_path(artifact):
    # Only generated opaque IDs name files; never use seller-provided filenames.
    if not re.fullmatch(r'artifact-[0-9a-f]{32}', artifact['id']):
        raise HTTPException(404,'File not found')
    path=ROOT/artifact['id']
    if path.is_symlink() or not path.is_file():raise HTTPException(404,'File not found')
    return path
