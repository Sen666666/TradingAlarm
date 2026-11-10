"""Independent checks of the packaged review atlas, not an account replay."""
from common_atlas import *
from collections import Counter
def loadz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def main():
 root=O/'web/data';index=loadz(root/'index.json.gz');original=pd.read_csv(ROUND/'comparison/campaigns.csv');expected={(r.sector,r.policy,r.scenario,r.symbol,r.entry_at):r for _,r in original.iterrows()};seen=set();receipts=set();counts=Counter();pnl=defaultdict_float={};prices={};ratings={};route_data={}
 for route in index['routes']:
  rid=route['id'];r=loadz(root/'paths'/f'{rid}.json.gz');route_data[rid]={c['id']:c for c in r['cycles']}
  assert len(r['cycles'])==route['cycles'];counts['routes']+=1
  for o in r['orders'].values():
   s=r['snapshots'][o['decision_at']];stage=s['stages'][o['stage']];sid=o['reserve']['sid'];assert sid in stage['priority'] and sid in stage['selected'];assert o['stock_rank']==stage['groups'][index['stocks'][sid]['sector_id']].index(sid)+1;assert o['sector_rank']==stage['sectors'].index(index['stocks'][sid]['sector_id'])+1
 for t in index['cycles']:
  key=(t['sector'],t['policy'],t['scenario'],t['symbol'],t['entry_at']);assert key in expected and key not in seen;seen.add(key);c=expected[key];assert abs(float(c.net_pnl)-t['net_pnl'])<1e-8 and abs(float(c.net_return)-t['net_return'])<1e-10
  rid=t['route'];d=route_data[rid][t['id']];r=loadz(root/'paths'/f'{rid}.json.gz') if False else None
  if t['symbol'] not in prices:
   p=loadz(root/'prices'/f'{t["symbol"]}.json.gz');prices[t['symbol']]={b[0]:b for b in p['bars']}
  bars=prices[t['symbol']];assert t['decision_at'] in bars
  rk=(t['sector'],t['decision_at'])
  if rk not in ratings:ratings[rk]=loadz(root/'ratings'/t['sector']/f'{t["decision_at"]}.json.gz')
  row=ratings[rk]['stocks'][t['symbol']];assert row[0]==t['RS'] and row[1]==t['pool_rank'];assert 1<=t['stock_rank']<=t['stock_count'] and 1<=t['sector_rank']<=t['sector_count']
  for f in d['fills']:
   k=(rid,f['receipt_id']);assert k not in receipts;receipts.add(k);day=f['at'][:10];b=bars[day];assert abs(f['causal_price']-f['raw_price']*b[6])<1e-8;assert abs(f['raw_price']*f['shares']-f['gross'])<1e-5;counts[f['side']+'_marks']+=1
   if f['side']=='buy':assert t['decision_at']<day
  assert d['fills'][0]['side']=='buy' and d['fills'][0]['at']==t['entry_at']
  if t['exit_at']:assert d['fills'][-1]['side']=='sell' and d['fills'][-1]['at']==t['exit_at']
  else:assert len(d['fills'])==1 and t['final_shares']>0;counts['open_cycles']+=1
  for p in d['protection']:assert p[0] in bars and t['entry_at'][:10]<=p[0]<=(t['exit_at'][:10] if t['exit_at'] else END)
  counts['cycles']+=1;counts['ranked_buy_explanations']+=1
  pnl[rid]=pnl.get(rid,0)+t['net_pnl']
 assert len(seen)==len(expected)==6340 and counts['buy_marks']==6340 and counts['sell_marks']==6303 and counts['open_cycles']==37
 for route in index['routes']:assert abs(pnl[route['id']]-route['net_return']*1000000)<1e-5
 for name,n in [('all-fills.csv',12643),('buy-rankings.csv',6340)]:assert len(pd.read_csv(root/name))==n
 source=read(O/'packaging-verification.json')['source_sha256']
 for p,h in source.items():assert sha(p)==h,p
 save(O/'atlas-verification.json',dict(passed=True,**counts,all_original_cycles_exact=True,all_account_net_pnl_exact=True,all_price_coordinates_exact=True,all_buy_rankings_and_stage_memberships_exact=True,all_original_sources_unchanged=True,economic_accounts_started=0))
 print(dict(counts),flush=True)
if __name__=='__main__':main()
