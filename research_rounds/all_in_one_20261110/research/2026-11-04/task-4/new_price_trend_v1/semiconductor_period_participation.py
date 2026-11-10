"""All126 evaluation identities; actual H1 wealth incl pre-H1 inventory.
No strategy changes, signals from labels, or account construction.
"""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import csv,gzip,hashlib,importlib.util,json,time
O=Path(__file__).resolve().parent;OUT=O/'analysis';Z=D(0);SRC={}
P=O/'analyze_saved_accounts.py';sp=importlib.util.spec_from_file_location('BB_H1_pure_saved_prices',P)
F=importlib.util.module_from_spec(sp);sp.loader.exec_module(F);A=F.A
def bind(p):p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def gz(p,lines=False):
 with gzip.open(bind(p),'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def n(x):return D(str(x))
def eq(a,b,tag):assert abs(a-b)<D('.000001'),(tag,a,b,a-b)

def analyze(mode,ids,old18,labels):
 root=O/'funding/runs'/('strong_'+mode);assert read(root/'DONE.json')['completed']
 b=gz(root/'pair/B.json.gz');ds=gz(root/'pair/daily.jsonl.gz',True);daily={r['at'][:10]:r for r in ds}
 begin,end='2025-12-31','2026-06-30';days=[d for d in sorted(daily)if begin<d<=end]
 native_periods=read(OUT/('strong_'+mode+'_PERIODS.json'));native_sectors=read(OUT/('strong_'+mode+'_INDUSTRIES.json'))
 expected=next(r for r in native_sectors if r['period']=='2026H1'and r['industry']=='半导体')
 cost=defaultdict(lambda:Z);buycount=defaultdict(int);cash={d:defaultdict(lambda:Z)for d in [begin,end]};div={d:defaultdict(lambda:Z)for d in [begin,end]}
 for t in b['trades']:
  sid=t['security_id']
  if sid not in ids:continue
  day=t['at'][:10];gross=n(t['gross_cny']);fee=n(t['fees_cny']);flow=-(gross+fee)if t['side']=='buy'else gross-fee
  for boundary in [begin,end]:
   if day<=boundary:cash[boundary][sid]+=flow
  if begin<day<=end and t['side']=='buy':cost[sid]+=gross+fee;buycount[sid]+=1
 for e in b['audit']:
  if e['kind']!='dividend_accrual':continue
  r=e['receivable'];sid=r['security_id']
  if sid not in ids:continue
  for boundary in [begin,end]:
   if r['ex_at'][:10]<=boundary:div[boundary][sid]+=n(r['net_local'])
 rows=[]
 for sid in sorted(ids):
  wealth={};inventory={}
  for boundary in [begin,end]:
   q=daily[boundary]['positions'].get(sid,0);inventory[boundary]=D(q)*A.price(sid,boundary)if q else Z
   wealth[boundary]=cash[boundary][sid]+div[boundary][sid]+inventory[boundary]
  held=[d for d in days if daily[d]['positions'].get(sid,0)]
  meanweight=sum((D(daily[d]['positions'][sid])*A.price(sid,d)/n(daily[d]['nav'])*100 for d in held),Z)/len(days)
  label=labels[sid]
  rows.append(dict(sid=sid,name=A.META[sid]['name'],in_original_H1_18=bool(sid in old18),
   H1_price_label=label['H1_price_return_pct'],H1_price_label_unknown=label['H1_price_return_pct']is None,
   actual_H1_held_CLOSEs=len(held),actual_H1_mean_NAV_weight_pct=meanweight,
   actual_pre_H1_inventory=inventory[begin],actual_H1_end_inventory=inventory[end],
   actual_H1_buy_cash=cost[sid],actual_H1_buy_fills=buycount[sid],actual_H1_wealth_change=wealth[end]-wealth[begin],
   actual_H1_contribution_pct_own_start_NAV=(wealth[end]-wealth[begin])/n(daily[begin]['nav'])*100))
 eq(sum((r['actual_H1_wealth_change']for r in rows),Z),n(expected['wealth_change']),(mode,'all126 wealth'))
 eq(sum((r['actual_H1_mean_NAV_weight_pct']for r in rows),Z),n(expected['mean_NAV_weight_pct']),(mode,'all126 meanweight'))
 result={}
 for name,a in [('all126',rows),('original18',[r for r in rows if r['in_original_H1_18']]),('other108',[r for r in rows if not r['in_original_H1_18']])]:
  result[name]=dict(stocks=len(a),actually_held_stocks=sum(r['actual_H1_held_CLOSEs']>0 for r in a),new_buy_stocks=sum(r['actual_H1_buy_fills']>0 for r in a),
   actual_buy_fills=sum(r['actual_H1_buy_fills']for r in a),buy_cash=sum((r['actual_H1_buy_cash']for r in a),Z),
   wealth_change=sum((r['actual_H1_wealth_change']for r in a),Z),mean_NAV_weight_pct=sum((r['actual_H1_mean_NAV_weight_pct']for r in a),Z),
   own_start_NAV=daily[begin]['nav'])
 save(mode+'_ALL126_H1_PERIOD_PARTICIPATION.json',rows)
 with(OUT/(mode+'_ALL126_H1_PERIOD_PARTICIPATION.csv')).open('w')as h:
  w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 return result

def main():
 start=time.monotonic();bind(__file__);bind(P);OUT.mkdir(exist_ok=True)
 original=read(O.parent/'SEMICONDUCTOR_ALL126_COMPARISON.json');labels={r['sid']:r for r in original if r['policy']=='PVR_NO60'}
 old18={r['sid']for r in read(O.parent/'POST_PURCHASE_ALL18_STOCKS.json')};assert len(labels)==126 and len(old18)==18
 ids=set(labels);out={mode:analyze(mode,ids,old18,labels)for mode in ['OFF','BB20']}
 save('SEMICONDUCTOR_H1_ACCOUNT_COMPARISON.json',out)
 for sid in A.frames:
  p=Path(A.SM[sid]['refs']['facts']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==A.SM[sid]['output_sha256'][str(p)];SRC[str(p)]=h
 SRC.update(F.MARK.sources);bind(O/'native_mark_reader.py')
 save('SEMICONDUCTOR_PERIOD_SOURCE_SHA256.json',SRC);save('SEMICONDUCTOR_PERIOD_SCOPE.json',dict(seconds=time.monotonic()-start,
  evaluation_only='All126 and all original18 fixed before current strategy planning; original price labels including12 unknown retained and never used in signals',
  money='Actual tradecash/dividend/mark wealth difference Dec31→Jun30 includes carried inventory; new-buy cost/fills and meanweight separate. Own H1 starting NAV differs by prior2025 account path.',
  accounts=0,new_labels=0))
 print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
