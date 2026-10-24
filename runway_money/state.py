"""Private durable plans, receipts, and process-safe single execution claims."""
import hashlib
import json
import os
from pathlib import Path
from contextlib import contextmanager
import fcntl
from decimal import Decimal

FIELDS = ('id', 'buyer', 'seller', 'purpose', 'amount_usd', 'path',
          'expected_cost', 'alternatives', 'drift', 'source')


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return format(Decimal(str(value)).normalize(), 'f')
    return value


def fingerprint(proposal):
    data = {k: proposal[k] for k in FIELDS}
    # Person C coerces path amounts to JSON numbers; normalize decimal strings.
    data = json.loads(json.dumps(data))
    for step in data['path']:
        step['amount'] = Decimal(str(step['amount']))
    for alt in data['alternatives']:
        for step in alt['path']:
            step['amount'] = Decimal(str(step['amount']))
    data = canonical(data)
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


class State:
    def __init__(self, directory='.runway/plans'):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, key):
        return self.root / (hashlib.sha256(key.encode()).hexdigest() + '.json')

    def read(self, key):
        return json.loads(self.path(key).read_text())

    def write(self, key, value):
        target = self.path(key)
        temp = target.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, target)

    def hold(self, evidence):
        self.write('__execution_hold__', evidence)

    def check_hold(self):
        if self.path('__execution_hold__').exists():
            raise RuntimeError('Live execution is on hold after a quote/fill mismatch; reconcile first')

    @contextmanager
    def lock(self, key):
        fd = os.open(str(self.path(key)) + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)
