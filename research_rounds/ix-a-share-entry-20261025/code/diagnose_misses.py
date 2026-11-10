"""Read-only annual winner opportunity diagnostics; no hypothetical profit sum."""
import gzip,json,collections
import pandas as pd
from util_ix import *

def main():
 out=HERE/'misses';out.mkdir(exist_ok=False);windows=read(OLD/'funnel-v2/qualified-annual-top20.json');assert len(windows)==240;write(out/'fixed-annual-top20.json',windows)
 targets={(w['symbol'],w['year']):w for w in windows};campaign=pd.read_csv(HERE/'analysis/campaigns.csv');cache={};trace=collections.defaultdict(lambda:dict(events=0,eligible=0,accepted=0,reasons=collections.Counter(),rejects=collections.Counter()))
 with gzip.open(HERE/'accounts/decisions.jsonl.gz','rt') as f:
  for line in f:
   d=json.loads(line);year=int(d['at'][:4]);events={e['symbol']:e for e in d['event_eligibility']};firstreject=dict(d['first_rejected']);execreject=dict(d['rejected'])
   for sid,e in events.items():
    if (sid,year) not in targets:continue
    key=d['account'],sid,year;z=trace[key];z['events']+=1;z['eligible']+=e['q'] is True;z['accepted']+=sid in d['accepted'];z['reasons'].update(e['reasons'])
    if sid in firstreject:z['rejects'][firstreject[sid]]+=1
    if sid in execreject:z['rejects'][execreject[sid]]+=1
 rows=[]
 for full in read(HERE/'accounts/summary.json')['accounts']:
  mode,aid=full.split('__',1)
  if not aid.endswith('_base'):continue
  for w in windows:
   sid,year=w['symbol'],w['year'];start=f'{year}-01-01';end=f'{year}-12-31';cc=campaign.loc[campaign.account.eq(full)&campaign.symbol.eq(sid)]
   participated=bool(((cc.entry_at.str[:10]<=end)&(cc.exit_at.fillna('9999').str[:10]>=start)).any())
   if sid not in cache:cache[sid]=pd.read_parquet(HERE/'signals'/f'{sid}.parquet')
   f=cache[sid].loc[start:end];z=trace[full,sid,year];reason=''
   if participated:reason='participated'
   elif f.empty or not f.strength_ready.any():reason='history_or_strength_not_ready'
   elif not f[mode].any():
    if mode=='W23' and f.W2H.any():reason='warm_jumped_to_expansion_not_exact_hot'
    elif mode in ['W23','W2H'] and f.C3.any():reason='crossed_hot_without_previous_warm'
    elif mode!='IX' and f.IX.any():reason='no_required_hot_transition'
    else:reason='no_IX_actionable_event'
   elif z['accepted']:reason='accepted_but_no_actual_fill_in_window'
   elif z['eligible']:
    reason=z['rejects'].most_common(1)[0][0] if z['rejects'] else 'eligible_not_allocated_or_no_cash'
   else:reason=z['reasons'].most_common(1)[0][0] if z['reasons'] else 'event_not_admitted'
   rows.append(dict(account=full,entry_scheme=mode,allocation=aid.split('_')[0],symbol=sid,name=w['name'],industry=w['industry'],year=year,posthoc_price_return=w['adjusted_price_return'],participated=participated,main_reason=reason,event_count=int(f[mode].sum()),raw_W23=int(f.raw_W23.sum()),raw_W2H=int(f.raw_W2H.sum()),raw_C3=int(f.raw_C3.sum()),eligible_event_days=z['eligible'],accepted_days=z['accepted'],qualification_reasons=dict(z['reasons']),constraint_reasons=dict(z['rejects'])))
 pd.DataFrame(rows).to_csv(out/'annual-winner-reasons.csv',index=False);write(out/'annual-winner-reasons.json',rows)
 a=pd.DataFrame(rows);s=a.groupby(['entry_scheme','allocation','main_reason']).size().reset_index(name='windows');s.to_csv(out/'reason-counts.csv',index=False);write(out/'summary.json',dict(recorded_at=now(),windows_per_account=240,base_accounts=16,rows=len(rows),counts=s.to_dict('records'),posthoc_only_not_selection=True,missed_returns_not_added_as_obtainable_profit=True))
 print(a.groupby(['entry_scheme','allocation']).participated.sum().to_string(),flush=True)

if __name__=='__main__':main()
