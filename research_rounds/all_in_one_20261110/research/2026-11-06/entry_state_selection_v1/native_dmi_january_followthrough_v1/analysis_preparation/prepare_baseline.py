"""Analyze sealed derived baseline outputs only. No account or strategy run."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib,ast
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
SRC=R/'act_only_ablation_continuous_v1/analysis'
OUT=Path(__file__).resolve().parent/'baseline_facts'
Z=D(0)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str,allow_nan=False))
def rows(name):return [r for r in csv.DictReader((SRC/name).open()) if r.get('account')=='PVR']
def dump(p,rr):
 if not rr:return
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rr for k in r)));w.writeheader();w.writerows(rr)
def stats(rows):
 pp=[D(r['pnl']) for r in rows];ww=[v for v in pp if v>0];ll=[v for v in pp if v<0];tt=[r for r in rows if D(r['pnl'])/D(r['buy_cost'])>=D('.30')]
 mw=sum(ww,Z)/len(ww) if ww else None;ml=sum(ll,Z)/len(ll) if ll else None
 return dict(n=len(pp),wins=len(ww),losses=len(ll),flat=len(pp)-len(ww)-len(ll),win_rate=len(ww)/len(pp) if pp else None,mean_win=mw,mean_loss=ml,payoff_ratio=mw/-ml if mw and ml else None,net_pnl=sum(pp,Z),fee_net_30pct_tail_count=len(tt),fee_net_30pct_tail_pnl=sum((D(r['pnl']) for r in tt),Z))
def main():
 OUT.mkdir(exist_ok=False)
 names=['STOCK_ROUNDS.csv','LAYER_ATTRIBUTION.csv','ANNUAL_METRICS.csv','ANNUAL_FEES_AND_BUY_PRINCIPAL.csv','SUMMARY.json','DAILY_RISK.csv']
 source={str(SRC/n):sha(SRC/n) for n in names};manifest=read(SRC/'OUTPUT_SHA256.json')
 for n in names:assert sha(SRC/n)==manifest[n],('sealed baseline derived output drift',n)
 rr=rows('STOCK_ROUNDS.csv');ll=rows('LAYER_ATTRIBUTION.csv');cohorts={};cr=[];cl=[];chains=[];tails=[]
 for year in ['2022','2026']:
  month=year+'-01';c=[r for r in rr if r['opened'].startswith(month)];ids={r['round_id'] for r in c};sids={r['sid'] for r in c};layers=[l for l in ll if l['round_id'] in ids and l['initial_layer']=='True'];closed=[r for r in c if r['closed']];opened=[r for r in c if not r['closed']];later=[r for r in rr if r['sid'] in sids and r['opened'][:10]>month+'-31'];lc=[r for r in layers if r['closed']]
  assert len(layers)==len(c)
  cohorts[year]=dict(account='PVR_ORIGINAL',cohort_definition='All actual 0-to-0 rounds whose first BUY occurred in this January; each distinct round preserved',cohort_rounds=len(c),unique_stocks=len(sids),within_January_repeat_rounds=len(c)-len(sids),complete_rounds=stats(closed),January_closed_rounds=stats([r for r in closed if r['closed'].startswith(month)]),post_January_closed_rounds=stats([r for r in closed if not r['closed'].startswith(month)]),open_rounds=len(opened),open_marked_pnl=sum((D(r['pnl']) for r in opened),Z),closed_initial_layers=stats(lc),open_initial_layers=len(layers)-len(lc),initial_closed_but_round_open=sum(l['closed'] and any(r['round_id']==l['round_id'] and not r['closed'] for r in c) for l in layers),last_close=max((r['closed'] for r in closed),default=None),closed_bookkeeping_UNKNOWN=0,external_actual_tradability_and_dividend_payout='UNKNOWN; retained rather than excluded',post_January_stock_set_reentries=len(later),post_January_stock_set_reentry_unique_stocks=len({r['sid'] for r in later}),post_January_stock_set_reentry_closed=stats([r for r in later if r['closed']]),post_January_stock_set_reentry_open=sum(not r['closed'] for r in later),reentry_denominator_warning='Later rounds are separate event chain, never pooled into original January win rate')
  cr.extend(dict(cohort=year,**r) for r in c);cl.extend(dict(cohort=year,**r) for r in layers)
  for sid in sorted(sids):
   seq=sorted([r for r in c+later if r['sid']==sid],key=lambda r:r['opened'])
   chains.extend(dict(cohort=year,sequence_for_sid=i+1,event_type='JANUARY_COHORT' if r['round_id'] in ids else 'POST_JANUARY_REENTRY',**r) for i,r in enumerate(seq))
  tails.extend(dict(cohort=year,**r) for r in closed if D(r['pnl'])/D(r['buy_cost'])>=D('.30'))
 summary=read(SRC/'SUMMARY.json')['summary']['PVR']
 save(OUT/'BASELINE_JANUARY_FOLLOWTHROUGH.json',dict(status='PVR_BASELINE_ONLY_NOT_DMI_RESULT',economic_runs=0,as_of='2026-05-15',cohorts=cohorts,full_account=summary,sources=source,comparability='2022 January versus 2026 January have different exposure horizons and inherited account states; not equal-maturity performance comparison'))
 dump(OUT/'BASELINE_JANUARY_ROUNDS.csv',cr);dump(OUT/'BASELINE_JANUARY_INITIAL_LAYERS.csv',cl);dump(OUT/'BASELINE_JANUARY_STOCK_EVENT_CHAINS.csv',chains);dump(OUT/'BASELINE_JANUARY_COMPLETE_TAILS.csv',tails)
 dump(OUT/'BASELINE_ANNUAL_NAV.csv',rows('ANNUAL_METRICS.csv'));dump(OUT/'BASELINE_ANNUAL_FEES.csv',rows('ANNUAL_FEES_AND_BUY_PRINCIPAL.csv'))
 dump(OUT/'BASELINE_JIANGFENG_KEMA_ROUNDS.csv',[r for r in rr if r['sid'] in ['300666.SZ','301611.SZ']])
 for p,h in source.items():assert sha(Path(p))==h
 save(OUT/'OUTPUT_SHA256.json',{p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps(cohorts,ensure_ascii=False,default=str))
if __name__=='__main__':main()
