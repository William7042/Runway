"""Save an offline pending preview when Person C's queue is not running.

This is not an approval queue and cannot approve or execute anything. Use the
normal CLI propose command once the real queue is available.
"""
import json
from pathlib import Path
from runway_money.router import build_router


class PreviewOnly:
    def create(self, proposal):
        path = Path('.runway/demo-proposal.json')
        path.write_text(json.dumps(proposal, indent=2))
        path.chmod(0o600)
        return proposal

    def approved(self, ident):
        raise RuntimeError('Offline preview cannot approve or execute; use Person C queue')


if __name__ == '__main__':
    router = build_router()
    router.queue = PreviewOnly()
    p = router.propose_payment('test', 'test2', '1',
        'Runway live demo: pay the test2 agent for a simulated research service',
        'Human requested a $1 test-to-test2 demo in this chat')
    print(json.dumps(p, indent=2))
