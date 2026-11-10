"""Independent saved-native audit. No strategy/account/guard import or replay.

This bounded checker deliberately requires no split/dividend in its small window;
those paths require separate native edge fixtures, not an assumed generic bridge.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import argparse,gzip,json,hashlib
import pandas as pd

O=Path(__file__).resolve().parent
BASE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/prepared-v2')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0);EPS=D('.000001');S=D('.0005');SRC={}
def n(v):return D(str(v))
def ts(v):return pd.Timestamp(str(v))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(Path(p).resolve())]=sha(p);return json.loads(Path(p).read_text())
def book(p):
 SRC[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt')as f:return json.load(f)
def rows(p):
 SRC[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt')as f:return[json.loads(x)for x in f]
def near(a,b,tag):assert abs(n(a)-n(b))<EPS,(tag,a,b,n(a)-n(b))

manifest={r['series_id']:r for r in read(BASE/'manifest.json')['series']}
facts={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
rawcache={};factcache={}
def raw(sid):
 if sid not in rawcache:
  r=manifest[sid]['files']['signal'];p=BASE/r['path'];assert sha(p)==r['sha256']
  SRC[str(p)]=sha(p);f=pd.read_parquet(p,columns=['raw_open','raw_close','observed_bar','synthetic_event_bar'])
  rawcache[sid]=f
 return rawcache[sid]
def mark(sid,at):
 f=raw(sid);ts=pd.Timestamp(str(at).replace('T',' '));d=pd.Timestamp(str(at)[:10]);i=f.index.searchsorted(d,side='right')-1
 while i>=0:
  r=f.iloc[i];rd=f.index[i]
  if bool(r.observed_bar)and not bool(r.synthetic_event_bar):
   col='raw_open'if rd==d and ts.hour<15 else'raw_close';v=n(r[col])
   if v.is_finite()and v>0:return v
  i-=1
 raise ValueError((sid,at,'unknown original raw mark'))
def factor(sid,at):
 if sid not in factcache:
  r=facts[sid];p=Path(r['refs']['facts']);assert sha(p)==r['output_sha256'][str(p)]
  SRC[str(p)]=sha(p);factcache[sid]=pd.read_parquet(p,columns=['factor'])
 return n(factcache[sid].loc[str(at)[:10],'factor'])

def prefix(b,cut):
 q={};basis={};pending={};cash=D('1000000');fees=Z;entry={};buyline={};divincome=Z;split_events=0
 tx={t['receipt_id']:t for t in b['trades']};txlayer={t['layer']:t['security_id']for t in b['trades']if t['side']=='buy'}
 for r in b['audit'][:cut]:
  k=r['kind']
  if k in ('split','split_fraction_floor_proxy'):
   sid=r['sid'];ratio=n(r['ratio']);ids=[i for i,v in q.items()if v and txlayer[i]==sid]
   target=int(sum(q[i]for i in ids)*ratio);parts=[int(D(q[i])*ratio)for i in ids];rem=target-sum(parts)
   for j in range(rem):parts[j%len(parts)]+=1
   for i,qty in zip(ids,parts):
    q[i]=qty;entry[i]/=ratio
    if not qty:basis[i]=Z
   split_events+=1
  elif k=='dividend_accrual':divincome+=n(r['receivable']['net_local'])
  if k=='reserve':
   assert r['order_id']not in pending
   pending[r['order_id']]=dict(sid=r['sid'],gross=n(r['gross_budget_cny']),fee=n(r['fee_reserved_cny']))
  elif k=='release_buy':
   o=pending.pop(r['order_id']);near(o['gross'],r['gross_released'],'release gross');near(o['fee'],r['fee_released'],'release fee')
  elif k=='fill':
   t=tx[r['receipt']['receipt_id']];gross=n(t['gross_cny']);fee=n(t['fees_cny']);fees+=fee
   near(sum(map(n,r['fee_components'].values()),Z),fee,'native fee component total')
   if t['side']=='buy':
    i=t['layer'];assert i not in q
    q[i]=int(t['shares']);basis[i]=gross+fee;entry[i]=gross/D(q[i]);buyline[i]=n(t['floor']);cash-=gross+fee
    o=pending[r['order_id']];o['gross']=n(r['gross_budget_remaining']);o['fee']=max(Z,o['fee']-fee)
   else:
    cash+=gross-fee;got=Z
    for part in t['parts']:
     i=part['layer'];count=int(part['shares']);assert 0<count<=q[i]
     basis[i]-=basis[i]*D(count)/D(q[i]);q[i]-=count;got+=n(part['net_cash'])
    near(got,gross-fee,'sale part cash')
 return dict(q=q,basis=basis,pending=pending,cash=cash,fees=fees,entry=entry,buyline=buyline,divincome=divincome,split_events=split_events)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 ds=rows(a.run/'pair/daily.jsonl.gz');bs=rows(a.run/'pair/balances.jsonl.gz');obs=read(a.run/'COST_OBSERVER_FINAL.json')
 end=max((str(r['at'])for r in ds),key=ts);arms=sorted({r['account']for r in ds});report={}
 for arm in arms:
  b=book(a.run/'pair'/f'{arm}.json.gz');daily=[r for r in ds if r['account']==arm]
  layer={x['id']:x for x in b['layers']};counts=Counter()
  for d in daily:
   at=str(d['at'])
   # Native audit is append-only; keep each event whose explicit clock is known.
   cut=0
   for i,r in enumerate(b['audit']):
    rt=str(r.get('at')or r.get('receipt',{}).get('at')or r.get('receivable',{}).get('ex_at')or '')
    if rt and ts(rt)>ts(at):break
    cut=i+1
   p=prefix(b,cut);quant=defaultdict(int)
   for lid,q in p['q'].items():quant[layer[lid]['sid']]+=q
   assert{sid:q for sid,q in quant.items()if q}==d['positions']
   inv=sum((D(q)*mark(sid,at)for sid,q in quant.items()if q),Z)
   near(inv,d['inventory'],'independent raw CLOSE inventory');near(p['cash']+p['divincome']+inv,d['nav'],'independent cash+dividend+inventory NAV')
   near(p['cash']+p['divincome'],n(d['available'])+n(d['order_reserved'])+n(d['sale_receivable'])+n(d['dividend_receivable']),'independent liquid+dividend bridge')
   near(p['fees'],d['fees_cny'],'cumulative actual fees');counts['financial_closes']+=1
  final=prefix(b,len(b['audit']));near(n(b['ending_NAV']),daily[-1]['nav'],'terminal')
  if arm!='B':
   for lid,v in final['basis'].items():near(v,obs[arm]['basis'][str(lid)],'final observed basis')
   events=rows(a.run/'pair'/f'{arm}-cost-guard.jsonl.gz');buyindex={r['receipt']['receipt_id']:i for i,r in enumerate(b['audit'])if r['kind']=='fill'}
   reserves={r['order_id']:i for i,r in enumerate(b['audit'])if r['kind']=='reserve'}
   trades={t['layer']:t for t in b['trades']if t['side']=='buy'}
   for e in events:
    if e['kind']not in('actual_reserve','actual_buy_fill'):continue
    if 'native_audit_count'in e:cut=e['native_audit_count']
    elif e['kind']=='actual_reserve':cut=reserves[e['order_id']]+1
    else:
     t=trades[e['layer']];cut=buyindex[t['receipt_id']]+1
     if cut<len(b['audit'])and b['audit'][cut]['kind']=='release_buy'and b['audit'][cut]['sid']==t['security_id']:cut+=1
    p=prefix(b,cut);at=e['at'];actual_layers={r['layer']:r for r in e['layers']};expect_live={i:q for i,q in p['q'].items()if q}
    assert{lid:int(r['qty'])for lid,r in actual_layers.items()}==expect_live
    used=protected=inv=Z
    prior=[d for d in daily if ts(d['at'])<ts(at)];prev=prior[-1]if prior else None;prevlayers={r['id']:r for r in prev['layers']}if prev else{}
    for lid,q in expect_live.items():
     r=actual_layers[lid];sid=layer[lid]['sid'];price=mark(sid,at);near(price,r['mark'],'original OPEN mark')
     near(p['basis'][lid],r['basis'],'actual-fill/part basis');near(p['entry'][lid],r['entry'],'actual entry')
     old=prevlayers.get(lid)
     line=n(old['last_core_line']if layer[lid]['kind']=='core'else old['floor'])if old else p['buyline'][lid]
     near(line/factor(sid,at),r['floor'],'OPEN uses prior-known line, not current CLOSE')
     hit=bool(r['known']and n(r['floor'])>=p['entry'][lid]and price>n(r['floor'])and not r['exit_locked']and e['release'])
     assert hit==r['protected']
     if hit:protected+=p['basis'][lid]
     else:used+=p['basis'][lid]
     inv+=D(q)*price
    pending=sum((o['gross']+o['fee']for o in p['pending'].values()),Z)
    drag=sum((o['fee']+o['gross']*S/(1+S)for o in p['pending'].values()),Z)
    nav=p['cash']+p['divincome']+inv
    for field,value in[('used_cost',used),('protected_cost',protected),('pending_cost',pending),('pending_drag',drag),('NAV',nav),('guard_NAV',nav-drag)]:near(value,e[field],field)
    assert used+pending<=n(e['alpha'])*(nav-drag)+EPS
    counts['atomic_saved_snapshots']+=1
  for r in bs:
   if r['account']==arm:
    for key in('independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference'):near(r[key],0,key)
  report[arm]=dict(counts,terminal_NAV=b['ending_NAV'],trades=len(b['trades']),basis_rebuilt_from_actual_callbacks=True,actual_split_events=final['split_events'],recognized_dividend=str(final['divincome']))
 # Exact no-op economic identity against the saved, already-completed No60 prefix.
 old=Path('pvr_pool_feasibility/runs')/('2022'if str(ds[0]['at'])[:4]=='2022'else'2025_26')/'pair';oldbook=book(old/'B.json.gz');newbook=book(a.run/'pair/B.json.gz')
 oldtr=[t for t in oldbook['trades']if ts(t['at'])<=ts(end)];assert oldtr==newbook['trades'],'NONE native trade prefix differs'
 olddaily=[r for r in rows(old/'daily.jsonl.gz')if ts(r['at'])<=ts(end)]
 assert olddaily==[r for r in ds if r['account']=='B'],'NONE native daily prefix differs'
 result=dict(status='PASS_SAVED_SMALL_FINANCE_AND_ATOMIC_COST_NOT_FINAL_TECHNICAL_GATE',run=str(a.run),arms=report,no_op_original_prefix_exact=True,
  limitations=['Native partial/CA edge-fixture coverage is separate from events actually present in this saved run.','This checker does not by itself certify source negative tests or cross-process restart.','No implementation or economic promotion inferred from small-window results.'],
  source_sha256=SRC,checker_sha256=sha(__file__))
 (a.out/'AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='source_sha256'},indent=2))
if __name__=='__main__':main()
