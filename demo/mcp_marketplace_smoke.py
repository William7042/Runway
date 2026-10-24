"""Exercise seller/buyer/bounty MCP flows against an isolated fake-money queue.

No real queue data is changed. Human approval and a clearly simulated receipt
are injected by this test harness, never through an agent approval tool.
"""
import asyncio
import os
from pathlib import Path
import subprocess
import tempfile
import socket
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from demo.mcp_smoke import ROOT, decode


async def main():
    with tempfile.TemporaryDirectory(prefix='runway-marketplace-') as temp:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        url=f'http://127.0.0.1:{port}'
        env={**os.environ,'QUEUE_DATA_FILE':str(Path(temp)/'store.json'),'STUB_EXECUTOR':'0'}
        proc=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-m','uvicorn','app:app',
            '--app-dir',str(ROOT/'product/queue_service'),'--host','127.0.0.1','--port',str(port),'--no-access-log'],
            cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    if httpx.get(url+'/health',timeout=.5).is_success: break
                except httpx.HTTPError: pass
                await asyncio.sleep(.1)
            else: raise RuntimeError('Isolated queue failed to start')
            params=StdioServerParameters(command=str(ROOT/'.venv/bin/python'),args=[str(ROOT/'mcp_server/server.py')],cwd=str(ROOT),
                env={'APPROVAL_QUEUE_URL':url,'RUNWAY_QUEUE_URL':url,'RUNWAY_MODE':'stub','DRY_RUN':'1'})
            async with stdio_client(params) as (r,w):
                async with ClientSession(r,w) as s:
                    await s.initialize()
                    names={t.name for t in (await s.list_tools()).tools}
                    assert not {'decide_proposal','attach_receipt','verify_bounty'} & names
                    async def call(name,args): return decode(await s.call_tool(name,args))
                    seller=await call('register_specialist',{'name':'Smoke reviewer','capability':'Review agent payment flows',
                        'price_usd':1,'payout_user':'test2','simulated':True})
                    token=seller['owner_token']
                    listings=await call('search_specialists',{'capability_query':'Smoke reviewer'})
                    assert any(p['id']==seller['id'] for p in listings)
                    args={'specialist_id':seller['id'],'buyer':'smoke-buyer','request':'Review the payment flow and return three risks','idempotency_key':'smoke-request-1234'}
                    job=await call('request_specialist_job',args)
                    assert job['proposal_id']
                    assert (await call('request_specialist_job',args))['id']==job['id']
                    assert (await call('list_specialist_jobs',{'specialist_id':seller['id'],'owner_token':token}))==[]
                    # Isolated human actor, not an exposed MCP approval tool.
                    response=httpx.post(url+f'/proposals/{job["proposal_id"]}/decision',json={'decision':'approve','reason':'isolated smoke-test human'})
                    response.raise_for_status()
                    preview=await call('execute_specialist_payment',{'job_id':job['id']})
                    assert preview['status']=='dry_run' and not preview['tx_hash']
                    assert not await call('list_specialist_jobs',{'specialist_id':seller['id'],'owner_token':token})
                    # Fake-money queue test only: explicit simulated payment evidence.
                    response=httpx.post(url+f'/proposals/{job["proposal_id"]}/receipt',json={'status':'executed','tx_hash':None,'quote':{'simulated':True},'fill':{'simulated':True}})
                    response.raise_for_status()
                    jobs=await call('list_specialist_jobs',{'specialist_id':seller['id'],'owner_token':token})
                    assert len(jobs)==1 and jobs[0]['status']=='paid'
                    await call('submit_specialist_result',{'job_id':job['id'],'owner_token':token,'result':'Simulated review: approval, net receipt, and replay checks.'})
                    assert (await call('get_specialist_job',{'job_id':job['id']}))['status']=='complete'
                    bounty=await call('post_bounty',{'title':'Smoke bounty','description':'Isolated demo task','price_usd':1})
                    claimed=await call('claim_bounty',{'bounty_id':bounty['id'],'claimant':'smoke-worker'})
                    assert claimed['status']=='claimed' and claimed['payment_warning']
                    submitted=await call('submit_bounty',{'bounty_id':bounty['id'],'submission':'Smoke work submitted; escrow remains unfunded.'})
                    assert submitted['status']=='submitted'
                    print('PASS: MCP register → discover → request → human approval → dry-run lock → simulated receipt → seller delivery')
                    print('PASS: MCP post → claim → submit bounty; no payout or real funds moved')
                    print('Agent tools:',len(names),'— financial approval and receipt tools absent')
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill();proc.wait()


if __name__=='__main__': asyncio.run(main())
