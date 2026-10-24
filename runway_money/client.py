"""SDK 0.3 compatibility: organization tokens do not include refresh_token."""
import os
import time
import httpx
from truemarkets import Client
from truemarkets.auth import load_key_file, sign_challenge
import json


class TrueMarketsError(RuntimeError):
    def __init__(self, status, path, data):
        self.status_code = status
        self.code = data.get('code')
        self.request_id = data.get('request_id')
        self.category = data.get('type')
        self.metadata = data.get('metadata', {})
        # Do not retain a request, response, headers, token or signing payload.
        self.api_message = data.get('message', 'Request failed')
        super().__init__(f'True Markets HTTP {status} at {path}: {self.api_message}')


class RunwayClient(Client):
    def __init__(self, **kwargs):
        os.environ.setdefault('TM_TELEMETRY', '0')
        super().__init__(**kwargs)

    def authenticate(self):
        if self._key is None:
            self._key_id, self._key = load_key_file(self.key_file)
        ts = int(time.time())
        r = httpx.post(f'{self.cfg.auth_base}/api-key/token', json={
            'key_id': self._key_id, 'timestamp': ts,
            'signature': sign_challenge(self._key, self._key_id, ts)}, timeout=30)
        if not r.is_success:
            raise RuntimeError(f'True Markets authentication HTTP {r.status_code}')
        tokens = r.json()
        self._access_token = tokens['access_token']
        self._refresh_token = tokens.get('refresh_token')
        self._authenticated_at = time.monotonic()

    def sign_turnkey(self, payload):
        raise RuntimeError('Sign only through the approval-guarded backend.submit')

    def request(self, method, path, *, user_id=None, body=None, params=None):
        """Current Gateway endpoints absent from the published SDK schema.

        Reuse SDK authenticated transport; never include response bodies in errors.
        """
        headers = {'TM-On-Behalf-Of': user_id} if user_id else {}
        if time.monotonic() - getattr(self, '_authenticated_at', 0) > 3300:
            self.authenticate()
        r = self._gateway_authed.get_httpx_client().request(
            method, self.cfg.base_url + path, headers=headers, json=body, params=params)
        if r.status_code >= 400:
            try:
                data = r.json()
            except ValueError:
                data = {}
            raise TrueMarketsError(r.status_code, path, data if isinstance(data, dict) else {})
        return r.json()

    def organization_id(self):
        import base64
        if not self._access_token:
            self.authenticate()
        raw = self._access_token.split('.')[1]
        claims = json.loads(base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)))
        return claims.get('organization_id') or claims['tm']['organization_id']

    def lookup_user(self, external_ref):
        org = self.organization_id()
        page = self.request('GET', f'/v1/account/organizations/{org}/users',
                            params={'external_ref_id': external_ref})
        users = page['data']
        if len(users) != 1:
            raise RuntimeError('Expected exactly one registered user for external_ref_id')
        return users[0]
