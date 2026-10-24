"""Read-only current Gateway access probe; private results stay ignored."""
import json
from pathlib import Path
from runway_money.client import RunwayClient

def main():
    out = {}
    with RunwayClient() as c:
        user = c.lookup_user('test')
        out['user'] = user
        uid = user['user_id']
        print('test user found; wallets:', len(user.get('wallets', [])))
        for path in ['/v1/gateway/assets', '/v1/gateway/balances',
                     '/v1/defi/core/assets', '/v1/defi/core/watchlists',
                     '/v1/defi/core/profile/me', '/v1/defi/core/history']:
            try:
                data = c.request('GET',path,user_id=uid)
                out[path] = data
                print(path, 'OK', list(data) if isinstance(data,dict) else f'{len(data)} items')
            except Exception as e:
                out[path] = {'error': str(e)}
                print(path, str(e))
    target=Path('.runway/gateway_access.json')
    target.write_text(json.dumps(out,indent=2)); target.chmod(0o600)

if __name__ == '__main__': main()
