"""Read-only account probe. No order preparation, signing, or execution."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
os.environ['TM_TELEMETRY'] = '0'
from runway_money.client import RunwayClient as Client


def plain(v):
    if hasattr(v, 'to_dict'):
        return v.to_dict()
    if isinstance(v, list):
        return [plain(x) for x in v]
    return v


def main():
    dest = Path('.runway')
    dest.mkdir(mode=0o700, exist_ok=True)
    results = {}
    with Client() as c:
        for namespace, op in [('gateway','list_assets'), ('defi','get_assets'),
                               ('defi','get_watchlists'), ('defi','get_profile'),
                               ('defi','get_balances'), ('defi','get_history')]:
            key = f'{namespace}.{op}'
            try:
                value = plain(getattr(getattr(c, namespace), op)())
                results[key] = value
                if isinstance(value, list):
                    print(key, 'items:', len(value))
                    if op == 'get_assets':
                        print('NVDAc catalog entries:', [x.get('symbol') for x in value if 'nvda' in str(x.get('symbol','')).lower()])
                elif isinstance(value, dict):
                    print(key, 'fields:', list(value))
                else:
                    print(key, type(value).__name__)
            except Exception as e:
                # Never echo exceptions: response bodies can contain account data.
                results[key] = {'error_type': type(e).__name__, 'http_status': getattr(e,'status_code',None)}
                print(key, results[key])
    target = dest / 'access.json'
    target.write_text(json.dumps(results, indent=2, default=str))
    target.chmod(0o600)

if __name__ == '__main__':
    main()
