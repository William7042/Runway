"""Unsigned quote only; deliberately no sign or execute methods."""
import json
from pathlib import Path
from runway_money.client import RunwayClient
with RunwayClient() as c:
 user=c.lookup_user('test'); uid=user['user_id']
 assets=c.request('GET','/v1/gateway/assets',user_id=uid)['data']
 sol=next(a for a in assets if a['symbol']=='SOL' and a['chain']=='solana')
 for endpoint,body in [('/v1/defi/core/quote',{'chain':'solana','base_asset':sol['address'],'quote_asset':'PYUSD','order_side':'buy','qty':'1','qty_unit':'quote','order_type':'market'})]:
  try:
   r=c.request('POST',endpoint,user_id=uid,body=body)
   Path('.runway/unsigned_quote.json').write_text(json.dumps(r,indent=2))
   print('quote fields',list(r)); print('quote summary',{k:v for k,v in r.items() if k not in ['payloads','web_authn_payload']})
  except Exception as e: print(type(e).__name__,str(e))
