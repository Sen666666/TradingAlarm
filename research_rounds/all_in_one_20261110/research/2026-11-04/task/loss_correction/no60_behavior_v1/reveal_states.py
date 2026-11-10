"""Stage two, six fixed cases: saved states and actual paths only."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import gzip,json,hashlib,importlib.util
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from raw_cases import CASES,P,W,sha
spec=importlib.util.spec_from_file_location('original_saved_cache_reader',W/'pvr-slot1-native-readiness-20261101/semiconductor-2026H1-readonly/analyze_readonly.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)
ROOTS={'PVR_BASELINE':W/'pvr-slot1-native-readiness-20261101/runs/2025_26/pair','PVR_NO60':P.parent.parent/'pvr_pool_feasibility/runs/2025_26/pair'}
SRC={};Z=D(0)
def clean(x):return S.clean(x)
def save(name,x):
 with (P/name).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False,default=str)
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def book(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return json.load(f)
def day(x):return str(x)[:10]
def n(x):return D(str(x))
def main():
 smp=W/'pvr-slot1-native-readiness-20261101/preflight-development-v1/SCORES_MANIFEST.json'
 scoremeta={x['symbol']:x for x in read(smp)['entries']};allout={};summ={}
 books={k:book(r/'B.json.gz') for k,r in ROOTS.items()};daily={k:rows(r/'daily.jsonl.gz') for k,r in ROOTS.items()}
 ops={k:rows(r/'opportunities.jsonl.gz') for k,r in ROOTS.items()};funds={k:rows(r/'funding.jsonl.gz') for k,r in ROOTS.items()}
 acts={k:read(P.parent/'pvr_no60_2025_26'/(k+'-ENTRY_ACTIONS.json')) for k in ROOTS}
 exits={k:read(P.parent/'pvr_no60_2025_26'/(k+'-EXIT_CHAIN.json')) for k in ROOTS}
 camps={k:read(P.parent/'pvr_no60_2025_26'/(k+'-CAMPAIGNS.json')) for k in ROOTS}
 derived={k:read(P.parent/'pvr_no60_2025_26/analysis/2025_26'/k/'LAYERS.json') for k in ROOTS}
 fig,axes=plt.subplots(6,3,figsize=(24,20),layout='constrained')
 for j,(sid,name,selection) in enumerate(CASES):
  f=S.frame(sid).loc['2025-07-01':'2026-06-30'];cp=Path(S.SM[sid]['refs']['CP1']);assert sha(cp)==S.SM[sid]['output_sha256'][str(cp)];SRC[str(cp)]=sha(cp);cz=pd.read_parquet(cp).loc[f.index]
  pp=W/f'pvr-slot1-native-readiness-20261101/preflight-development-v1/scores/{sid}.parquet';assert sha(pp)==scoremeta[sid]['output_sha256'];SRC[str(pp)]=sha(pp);pv=pd.read_parquet(pp).score.reindex(f.index)
  sec=S.META[sid]['sector_id'];sp=Path(S.IM[sec]['refs']['state']);assert sha(sp)==S.IM[sec]['output_sha256'][str(sp)];SRC[str(sp)]=sha(sp);st=pd.read_parquet(sp).set_index('day')
  states=f.join(cz.add_prefix('CP1_')).join(pv.rename('PVR_score'));states.to_csv(P/(sid+'-SAVED_STATES.csv'))
  own=dict(sid=sid,name=S.META[sid]['name'],selection=selection,sector=sec,cached_daily_states=clean(states.reset_index().to_dict('records')),industry_states=clean(st.loc['2025-07-01':'2026-06-30'].reset_index().to_dict('records')),policies={})
  ii=np.arange(len(f));xd={str(t.date()):k for k,t in enumerate(f.index)}
  for a in axes[j]:a.plot(ii,f.close,color='#384957',lw=1);a.grid(alpha=.15);ticks=np.arange(0,len(f),45);a.set_xticks(ticks,[str(f.index[k].date()) for k in ticks],fontsize=7,rotation=10)
  axes[j,0].plot(ii,f.i_floor.where(f.i_target.astype(bool)),color='#308f6b',lw=1,label='original I/E0 line')
  receipt=cz.receipt.astype(bool);axes[j,0].scatter(ii[receipt],cz.candidate[receipt],s=12,color='#b5681c',label='fresh CP1 candidate')
  axes[j,0].set_title(f'{sid} {name}: cached I + CP1',fontsize=10);axes[j,0].legend(fontsize=7)
  v=axes[j,0].twinx();v.plot(ii,pv,color='#a9b5c0',alpha=.5,lw=.7);v.set_ylim(0,100);v.set_ylabel('saved PVR',fontsize=7)
  for col,(policy,b) in enumerate(books.items(),1):
   trades=[t for t in b['trades'] if t['security_id']==sid];layers=[l for l in b['layers'] if l['sid']==sid];jr={x['layer']:x for x in b['journal'] if x['kind']=='real_buy_fill' and x['sid']==sid};lm={x['layer']:x for x in derived[policy] if x['sid']==sid};aa={x['layer']:x for x in acts[policy] if x['sid']==sid};buys={t['layer']:t for t in trades if t['side']=='buy'}
   dd={day(r['at']):r for r in daily[policy]};layerpaths=[]
   for l in layers:
    lid=l['id'];t=buys[lid];sg=day(t['signal_at']);bd=day(t['at']);r=S.frame(sid).loc[pd.Timestamp(bd)];factor=n(r.factor);pf=n(t['floor']);initialraw=pf/factor;series=[]
    for d,rw in dd.items():
     z=next((x for x in rw['layers'] if x['id']==lid),None)
     if z:
      rr,obs=S.row(sid,d);fl=z['last_core_line'] if z['role']=='core' else z['floor'];series.append(dict(day=d,qty=z['qty'],role=z['role'],pool=z['pool'],active_actual_floor=n(fl),actual_raw_floor=n(fl)/n(rr.factor),cached_close=n(rr.close),cached_raw_close=n(rr.raw_close),source_day=obs))
    es=[x for x in exits[policy] if x['layer']==lid];ss=[x for x in trades if x['side']=='sell' and any(z['layer']==lid for z in x['parts'])]
    # Accepted signal floor is from the original fill, never final raised floor.
    end=day(l['closed']) if l['closed'] else '2026-06-30';segment=f.loc[bd:end]
    if l['closed']:segment=segment.loc[segment.index<pd.Timestamp(end)]
    prior=f.loc[:sg];cost_adj=n(t['price'])*factor
    progress=dict(continuous_entry_price=cost_adj,entry_frozen_floor=pf,maximum_observed_close_while_open=n(segment.close.max()) if len(segment) else None,maximum_close_above_actual_entry_pct=(n(segment.close.max())/cost_adj-1)*100 if len(segment) else None,saved_fresh_receipts_while_open=int(cz.loc[segment.index].receipt.sum()),actual_floor_max_above_initial=max((x['active_actual_floor']-pf for x in series),default=Z),interpretation='descriptive after actual path, not a policy; actual exit is OPEN, so exit-day CLOSE is excluded; daily close floor can be post-update and request clocks must be checked')
    layerpaths.append(dict(layer=lid,entry_action=aa[lid],actual_fill=t,initial_adjusted_floor=pf,initial_raw_floor_at_fill=initialraw,floor_clock='original frozen signal floor / entry-day known factor',initial_price_to_floor_raw=n(t['price'])-initialraw,frozen_signal_state=S.state(sid,sg),entry_day_state_not_used_for_buy=S.state(sid,bd),fill_journal=jr[lid],original_terminal_layer=l,original_financial_attribution=lm[lid],actual_exit_requests=es,actual_sell_parts=ss,after_close_actual_layer_state=series,descriptive_progress=progress))
    y=n(t['price'])*factor;axes[j,col].scatter(xd[bd],float(y),marker='^',s=27,color='#d65342',zorder=5)
    if series:axes[j,col].plot([xd[x['day']] for x in series if x['day'] in xd],[float(x['active_actual_floor']) for x in series if x['day'] in xd],lw=.7,alpha=.65,color='#337f99' if jr[lid]['role']=='mobile' else '#8c70ab')
   for t in trades:
    if t['side']=='sell':
     d=day(t['at']);r,obs=S.row(sid,d);axes[j,col].scatter(xd[d],float(n(t['price'])*n(r.factor)),marker='v',s=24,color='#2e8f69',zorder=5)
   own['policies'][policy]=dict(layers=layerpaths,actual_campaigns=[x for x in camps[policy] if x['sid']==sid],actual_opportunities=[x for x in ops[policy] if x['sid']==sid],actual_funding=[x for x in funds[policy] if x['sid']==sid],all_decision_intents=[dict(at=d['at'],nav=d['nav'],on=d['on'],intent=i) for d in b['decisions'] for i in d['intents'] if i['sid']==sid],actual_exit_requests=[x for x in exits[policy] if x['sid']==sid])
   summ.setdefault(sid,{})[policy]=dict(buys=len(buys),buy_cost=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in buys.values()),Z),net=sum((n(x['net']) for x in lm.values()),Z),entry_actions=dict(Counter(aa[x]['action'] for x in aa)),exit_reasons=dict(Counter(x['reason'] for x in exits[policy] if x['sid']==sid)),layers=[dict(layer=x['layer'],opened=x['actual_fill']['at'],action=x['entry_action']['action'],role=x['fill_journal']['role'],pool=x['fill_journal']['pool'],initial_floor=x['initial_adjusted_floor'],initial_raw_floor=x['initial_raw_floor_at_fill'],cost=x['original_financial_attribution']['cost'],net=x['original_financial_attribution']['net'],qty=x['original_terminal_layer']['qty'],exit_reason=x['original_terminal_layer'].get('reason'),closed=x['original_terminal_layer']['closed'],**x['descriptive_progress']) for x in layerpaths])
   axes[j,col].set_title(policy+' actual fills + live floors (after CLOSE)',fontsize=10)
  allout[sid]=own;save(sid+'-FULL_SAVED_PATH.json',own)
 fig.savefig(P/'SIX_SAVED_STATE_AND_ACTUAL_PATHS.png',dpi=135);plt.close(fig)
 save('SIX_PATH_SUMMARY.json',summ);src=dict(SRC);src.update(S.SRC);src[str(Path(__file__))]=sha(__file__)
 save('SAVED_PATH_SOURCE_BINDING.json',dict(sources=src,new_signal_computations=0,new_account_events=0,case_membership=CASES,comparison='two endogenous policies; no matched-layer causality claimed'))
 print(json.dumps(clean(summ),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
