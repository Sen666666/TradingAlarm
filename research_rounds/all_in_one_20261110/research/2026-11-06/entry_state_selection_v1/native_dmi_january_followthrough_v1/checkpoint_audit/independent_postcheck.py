"""Independent sealed ledger audit; never creates a strategy Runner/Account or executes account events."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
from datetime import datetime
import json,gzip,hashlib,csv,math,sys
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'native_dmi_january_followthrough_v1';OLD=R/'native_dmi_two_month_continuous_v1';BASE=R/'act_only_ablation_continuous_v1/run'
Z=D(0);EPS=D('1e-8')
def j(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
def seal(p,m):
 v=j(p/m)
 for n,h in v.items():assert sha(Path(n) if Path(n).is_absolute() else p/n)==h,(p,n,'seal drift')
 return {'sha256':sha(p/m),'entries':len(v)}
def timeline(a):
 qty=defaultdict(int); live={}; rr=[]; owner={}; lc=defaultdict(lambda:Z); layerqty={}; ls={l['id']:l for l in a['layers']}
 ev=[(datetime.fromisoformat(t['at']),0,i,t) for i,t in enumerate(a['journal']) if t['kind']=='actual_split']+[(datetime.fromisoformat(t['at']),1,i,t) for i,t in enumerate(a['trades'])]
 for at,kind,i,t in sorted(ev,key=lambda x:x[:3]):
  if kind==0:
   sid=t['sid']; ks=[k for k,q in layerqty.items() if q and ls[k]['sid']==sid]; old=qty[sid]; rat=D(t['ratio']); target=int(D(old)*rat); parts=[int(D(layerqty[k])*rat) for k in ks]
   for n in range(target-sum(parts)):parts[n%len(parts)]+=1
   for k,q in zip(ks,parts):layerqty[k]=q
   qty[sid]=target
  else:
   sid=t['security_id']
   if t['side']=='buy':
    if not qty[sid]:
     rr.append(dict(sid=sid,opened=t['at'],closed=None,first=t['layer'],layers=[]));live[sid]=rr[-1]
    r=live[sid];k=t['layer'];assert k not in owner;owner[k]=r;r['layers'].append(k);layerqty[k]=t['shares'];qty[sid]+=t['shares'];lc[k]-=D(t['gross_cny'])+D(t['fees_cny'])
   else:
    assert qty[sid]>=t['shares']>0
    assert sum(p['shares'] for p in t['parts'])==t['shares']
    assert abs(sum((D(p['net_cash']) for p in t['parts']),Z)-(D(t['gross_cny'])-D(t['fees_cny'])))<EPS
    for p in t['parts']:
     k=p['layer'];assert owner[k] is live[sid];layerqty[k]-=p['shares'];assert layerqty[k]>=0;lc[k]+=D(p['net_cash'])
    qty[sid]-=t['shares']
    if qty[sid]==0:live.pop(sid)['closed']=t['at']
 for k,l in ls.items():
  assert layerqty[k]==l['qty'],(k,'qty')
  assert abs(lc[k]-D(l['cash']))<EPS,(k,'cash',lc[k],l['cash'])
 for r in rr:
  r['cash']=sum((lc[k] for k in r['layers']),Z);r['dividend']=sum((D(ls[k]['dividend']) for k in r['layers']),Z);r['buy_cost']=sum((D(t['gross_cny'])+D(t['fees_cny']) for t in a['trades'] if t['side']=='buy' and t['layer'] in r['layers']),Z)
  assert bool(r['closed'])==(sum(layerqty[k] for k in r['layers'])==0)
 return rr,{s:q for s,q in qty.items() if q},ls
def main(year,analysis):
 path=O/(year+'Jan_DMI');done=j(path/'DONE.json');out={'branch':year,'economic_runs':0,'output_seal':seal(path,'OUTPUT_SHA256.json'),'analysis_seal':seal(analysis,'OUTPUT_SHA256.json')}
 assert done['completed'] and done['study_freeze_sha256']==sha(O/'STUDY_FREEZE.json')
 assert sha(O/'PARENT_RELEASE.json')=='d44866fdbfb3666c9b10b95510e852760bf42a6a3a6d1b0bccaefae440b11eea'
 md=j(path/'final_checkpoint/checkpoint.json');assert md['sha256']==sha(path/'final_checkpoint/checkpoint.pkl')
 for p,h in md['source_freeze'].items():assert sha(p)==h,(p,'final checkpoint source')
 out['checkpoint_seal_sources']=len(md['source_freeze'])
 a=gz(path/'pair/PVR.json.gz');mo=gz(OLD/(year+'Jan_DMI')/'pair/PVR.json.gz');base=gz(BASE/'pair/PVR.json.gz')
 for key in ['trades','decisions','audit','journal']:assert a[key][:len(mo[key])]==mo[key],(key,'monthly prefix')
 if year=='2026':
  for key in ['trades','decisions','journal']:
   left=[x for x in a[key] if x['at'][:10]<'2026-01-01'];right=[x for x in base[key] if x['at'][:10]<'2026-01-01'];assert left==right,(key,'PVR ancestry')
  out['pre_2026_PVR_ancestry_exact']=True
 ds=rows(path/'pair/daily.jsonl.gz');ms=rows(OLD/(year+'Jan_DMI')/'pair/daily.jsonl.gz');assert ds[:len(ms)]==ms
 bd=[r for r in rows(BASE/'pair/daily.jsonl.gz') if r['account']=='PVR'];want=[r['at'] for r in bd if r['at'][:10]>ms[-1]['at'][:10]]
 assert [r['at'] for r in ds[len(ms):]]==want and len(want)==done['suffix_days'];assert len({r['at'] for r in ds})==len(ds)
 for d in ds:
  assert sum((D(d[k]) for k in ['available','order_reserved','settlement_locked','sale_receivable','dividend_receivable','inventory']),Z)-D(d['payable'])==D(d['nav'])
  qq=defaultdict(int)
  for l in d['layers']:qq[l['sid']]+=l['qty']
  assert dict(qq)==d['positions'];assert D(d['available'])>=0
 bal=rows(path/'pair/balances.jsonl.gz')
 for b in bal:
  for k in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']:assert abs(D(str(b[k])))<EPS,(b['at'],k)
  assert all(abs(D(str(v)))<EPS for v in b['pool_occupancy_difference'].values())
 checks=rows(path/'OPEN_CASH_CHECKS.jsonl.gz');assert len(checks)==len(ds)
 assert all(D(x['cash_gap'])==0 and D(x['pending_reserve'])==0 for x in checks)
 fills=rows(path/'SHARED_WINDOW_AUDIT.jsonl.gz');suff=a['trades'][len(mo['trades']):];assert len(fills)==len(suff)
 for f,t in zip(fills,suff):
  assert f['sid']==t['security_id'] and f['side']==t['side'] and datetime.fromisoformat(f['at'])==datetime.fromisoformat(t['at'])
  assert f['prior_volume_last']<f['at'][:10] and f['unknown_tradability'];assert D(f['raw_open'])==D(t['raw_open']) and D(f['price'])==D(t['price'])
  assert D(t['price'])==D(t['raw_open'])*(D('1.0005') if t['side']=='buy' else D('.9995'))
 assert sum((D(t['fees_cny']) for t in a['trades']),Z)==D(ds[-1]['fees_cny'])
 rank=rows(path/'DMI_RANK_AUDIT.jsonl.gz');feat=pd.read_parquet(O/'ALL_CONTINUATION_DMI_FEATURES.parquet').set_index(['sid','day']).d
 by=defaultdict(list)
 for x in rank:
  d=feat.loc[(x['sid'],x['day'])];assert (x['d'] is None and pd.isna(d)) or x['d']==d
  expected=(not x['held']) and x['industry_active'] and x['PVR'] is not None and math.isfinite(x['PVR']) and x['d'] is not None
  assert x['mutable']==expected
  if not expected:assert x['rank']==x['original_PVR_rank']
  by[x['day']].append(x)
 assert set(by)=={r['at'][:10] for r in ds[len(ms):]}
 for day,rs in by.items():
  assert len({r['sid'] for r in rs})==len(rs)
  groups=defaultdict(list)
  for r in rs:
   if r['mutable']:groups[(r['sector'],tuple(r['roles']))].append(r)
  for g in groups.values():
   ordered=sorted(g,key=lambda r:(-r['d'],-r['PVR'],r['sid']))
   assert [r['rank'] for r in ordered]==sorted(r['original_PVR_rank'] for r in g),(day,'rank')
 out['native_checks']={'daily_rows':len(ds),'suffix_days':len(want),'trade_prefix':len(mo['trades']),'suffix_fills':len(fills),'open_cash_rows':len(checks),'all_balance_and_NAV_gaps_zero':True,'rank_rows':len(rank),'UNKNOWN_fixed_slots':sum(r['d'] is None for r in rank),'all_CLOSED_days_DMI_rank_reconstructed':True}
 rr,pos,ls=timeline(a);mr,_,_=timeline(mo);cc=[r for r in rr if r['opened'].startswith(year+'-01')];mcc=[r for r in mr if r['opened'].startswith(year+'-01')]
 assert [(r['sid'],r['opened'],r['first']) for r in cc]==[(r['sid'],r['opened'],r['first']) for r in mcc]
 assert pos==ds[-1]['positions']
 # Read only original market/price provider, never instantiate an economic Account or Runner.
 sys.path.insert(0,str(R/'account_comparison_continuous_v1/inputs'));import continuous_inputs as C
 ids=j(C.U/'FREEZE.json')['stocks'];bundle,market,_=C.J.M.context('2026-05-15',ids=ids);at=datetime.fromisoformat(ds[-1]['at']);marks=market.marks(at,pos)
 values={s:mk.cny_price(at)*D(pos[s]) for s,mk in marks.items()};assert sum(values.values(),Z)==D(ds[-1]['inventory'])
 stale=[]
 for sid,mk in marks.items():
  raw=market.raw[sid].loc[:'2026-05-15'];eligible=raw[raw.valid_price & raw.observed_bar];last=eligible.index[-1].date().isoformat()
  assert mk.known_at.date().isoformat()==last
  if last!='2026-05-15':stale.append({'sid':sid,'last':last,'value':str(values[sid])})
 for r in rr:r['pnl']=r['cash']+r['dividend']+sum((D(ls[k]['qty'])*marks[ls[k]['sid']].cny_price(at) for k in r['layers'] if ls[k]['qty']),Z)
 assert abs(sum((r['pnl'] for r in rr),Z)-(D(ds[-1]['nav'])-D(1200000)))<EPS
 div=sum((D(x['receivable']['net_local']) for x in a['audit'] if x['kind']=='dividend_accrual'),Z)
 assert div==sum((D(l['dividend']) for l in ls.values()),Z)
 summary=j(analysis/'SUMMARY.json');co=summary['January_cohorts']['DMI_FROM_'+year+'JAN_'+year];cl=[r for r in cc if r['closed']]
 assert len(cc)==co['cohort_rounds'] and len(cl)==co['complete_rounds']['n']
 assert sum(r['pnl']>0 for r in cl)==co['complete_rounds']['wins']
 assert abs(sum((r['pnl'] for r in cl),Z)-D(co['complete_rounds']['net_pnl']))<EPS
 first=[ls[r['first']] for r in cc];fc=[l for l in first if l['qty']==0]
 assert len(fc)==co['closed_first_BUY_layers']['n']
 assert sum(D(l['cash'])+D(l['dividend'])>0 for l in fc)==co['closed_first_BUY_layers']['wins']
 assert abs(sum((D(l['cash'])+D(l['dividend']) for l in fc),Z)-D(co['closed_first_BUY_layers']['net_pnl']))<EPS
 tails=[r for r in cl if r['pnl']/r['buy_cost']>=D('.3')];assert len(tails)==co['complete_rounds']['fee_net_30pct_tail_count']
 out['cohort']={'fixed_members':len(cc),'closed':len(cl),'wins':sum(r['pnl']>0 for r in cl),'net_closed_pnl':str(sum((r['pnl'] for r in cl),Z)),'first_closed':len(fc),'first_wins':sum(D(l['cash'])+D(l['dividend'])>0 for l in fc),'first_pnl':str(sum((D(l['cash'])+D(l['dividend']) for l in fc),Z)),'open':[dict(sid=r['sid'],opened=r['opened'],first=r['first'],pnl=str(r['pnl']),quantity=sum(ls[k]['qty'] for k in r['layers'])) for r in cc if not r['closed']],'tails':[dict(sid=r['sid'],opened=r['opened'],pnl=str(r['pnl'])) for r in tails]}
 out['final']={'nav':ds[-1]['nav'],'cash':ds[-1]['available'],'inventory':ds[-1]['inventory'],'dividend_receivable':ds[-1]['dividend_receivable'],'all_dividend_accrual':str(div),'fees':ds[-1]['fees_cny'],'held':len(pos),'live_layers':len(ds[-1]['layers']),'pending':ds[-1]['pending_intents'],'stale':stale,'last_event':md['at'],'NAV_PnL_all_round_bridge_pass':True}
 out['passed']=True;print(json.dumps(out,indent=2));return out
if __name__=='__main__':
 y=sys.argv[1];p=Path(sys.argv[2]);result=main(y,p)
 if len(sys.argv)>3:
  dest=Path(sys.argv[3]);assert not dest.exists();dest.write_text(json.dumps(result,indent=2))
