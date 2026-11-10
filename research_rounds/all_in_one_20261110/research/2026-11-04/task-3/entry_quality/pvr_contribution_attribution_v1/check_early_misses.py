"""Bounded explanation of early missed large episodes; no full reranking."""
from pathlib import Path
import json,hashlib,time
import numpy as np,pandas as pd
B=Path(__file__).resolve().parent;C=B.parent/'daily_signal_cache_pilot20_v1/full_universe_v1';w=.9**np.arange(20,-1,-1);w/=w.sum()
def dump(n,x):(B/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 tick=time.time();r=pd.read_parquet(B/'FULLQUEUE_SELECTED_STOCKDAYS.parquet');r=r.loc[(r.period=='2024_2026_seen')&(r.cap=='top20pct')&(r.h==60)&(r.age<=5)].copy();x=pd.read_parquet(B/'ALL_BUY_ATTRIBUTIONS.parquet');entry=pd.read_parquet(B/'EVENT_COHORTS_MECHANISM.parquet');entry=entry.loc[entry.cohort.eq('entry0')&entry.period.eq('2024_2026_seen')]
 big=set(entry.loc[entry.big60.eq(1),'episode_id']);fail=set(entry.loc[entry.fail_rebound20.eq(1)&entry.big60.eq(0),'episode_id']);base=r.loc[r.ranker.eq('E')].sort_values('day').drop_duplicates('episode_id');altset=set(r.loc[r.ranker.eq('E_support'),'episode_id']);base=base.merge(x,on=['sid','day','episode_id','age','year','period'],suffixes=('','_x'),validate='one_to_one')
 lost=base.loc[base.episode_id.isin(big)&~base.episode_id.isin(altset)].copy();kept=base.loc[base.episode_id.isin(big)&base.episode_id.isin(altset)].copy();flost=base.loc[base.episode_id.isin(fail)&~base.episode_id.isin(altset)].copy();assert len(lost)==330
 # Greedy unique matched controls from retained large episodes, exact date/2-point PVR bin/I age.
 controls=[];used=set();matched=[]
 for _,a in lost.sort_values(['day','sid']).iterrows():
  q=kept.loc[kept.day.eq(a.day)&kept.pvrbin.eq(a.pvrbin)&kept.age.eq(a.age)&~kept.episode_id.isin(used)].copy()
  if len(q):
   q['gap']=abs(q.score-a.score);v=q.sort_values(['gap','sid']).iloc[0].copy();v['matched_lost_ep']=a.episode_id;controls.append(v);used.add(v.episode_id);matched.append(a.episode_id)
 # All failed-only removals remain bounded by selected early event sets; no whole-universe scan.
 lost['group']='lost_large330';keptc=pd.DataFrame(controls);keptc['group']='matched_kept_large';flost['group']='lost_failed_only';lost['has_matched_control']=lost.episode_id.isin(matched)
 q=pd.concat([lost,keptc,flost],ignore_index=True);out=[];sources={}
 dump('EARLY_MISS_FREEZE.json',dict(status='BOUNDED_POST_OUTCOME_EXPLANATION_NOT_PREDICTIVE_VALIDATION',groups=dict(lost_large=len(lost),matched_retained_large=len(keptc),lost_failed_only=len(flost)),first_break='Current close > max prior20 closes and no earlier observation in this original I episode did so. Uses only <=t.',hypothesis='E_fresh=E-A_up*(1-max(P5,FirstBreakInI)); no extra weighted factors. This preserves original up-amount amplification at first20-close-high in I.',guarantee='If a row selected in original E topN is restored exactly to E while all revised candidates remain <=their original E, it must remain selected under identical universe and sid tie-break. Count this sufficient recovery condition only; do not call it full performance.',code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
 for sid,part in q.groupby('sid'):
  a=pd.read_parquet(C/'artifacts'/f'{sid}.parquet',columns=['day','source_row_present','price__close','pvr__e','pvr__u','pvr__b','pvr__scale']);a=a.loc[a.source_row_present].reset_index(drop=True);c=a.price__close;prior=c.shift().rolling(20,min_periods=20).max();br=c>prior;lookup={d:i for i,d in enumerate(a.day)}
  for _,row in part.iterrows():
   i=lookup[row.day];st=lookup[pd.Timestamp(row.entry_day)];assert i-st==row.age
   hh=c.iloc[i-24:i-4].max();p5=float((c.iloc[i-4:i+1]>hh).mean());window=a.iloc[i-20:i+1];u=window.pvr__u.to_numpy();b=window.pvr__b.to_numpy();up=w*.5*u*abs(u)*b*((u>0)&(b>0));A=up.sum();first=bool(br.iloc[i]and int(br.iloc[st:i+1].sum())==1)
   support=float(50+50*np.tanh(2*(row.E-A*(1-p5))));z=row.to_dict();z.update(hold5=p5,A_up=A,E_discount=A*(1-p5),new20high=bool(br.iloc[i]),first20high_in_I=first,break_distance=float(np.log(c.iloc[i]/prior.iloc[i])/a.pvr__scale.iloc[i]),max_up_amount_age=int(20-up.argmax()),max_up_amount_share=float(up.max()/A)if A>0 else np.nan,discount_score=float(row.score-support),score_support=support);out.append(z)
 f=pd.DataFrame(out);f.to_csv(B/'EARLY_MISS_CASE_FEATURES.csv',index=False);summary=[]
 for name,g in f.groupby('group'):
  summary.append(dict(group=name,N=len(g),stocks=g.sid.nunique(),dates=g.day.nunique(),age0=int(g.age.eq(0).sum()),age_median=g.age.median(),hold0=int(g.hold5.eq(0).sum()),hold_le02=int(g.hold5.le(.2).sum()),hold_median=g.hold5.median(),current_new20high=int(g.new20high.sum()),first20high_in_I=int(g.first20high_in_I.sum()),first_with_hold_le02=int((g.first20high_in_I&g.hold5.le(.2)).sum()),A_up_median=g.A_up.median(),score_discount_median=g.discount_score.median(),break_distance_median=g.break_distance.median(),max_up_amount_age_median=g.max_up_amount_age.median(),signal_ret20_mean=g.ret20.mean(),signal_ret60_mean=g.ret60.mean()))
 pd.DataFrame(summary).to_csv(B/'EARLY_MISS_GROUP_SUMMARY.csv',index=False)
 # Matched diagnostic differences; same outcome-class design is explanatory, not outcome predictive contrast.
 pairs=[];l=f.loc[f.group.eq('lost_large330')].set_index('episode_id')
 for _,b in f.loc[f.group.eq('matched_kept_large')].iterrows():
  a=l.loc[b.matched_lost_ep];pairs.append(dict(day=a.day,lost=a.sid,kept=b.sid,age=a.age,score_gap=a.score-b.score,lost_hold=a.hold5,kept_hold=b.hold5,hold_diff=a.hold5-b.hold5,lost_A_up=a.A_up,kept_A_up=b.A_up,A_up_diff=a.A_up-b.A_up,lost_first=bool(a.first20high_in_I),kept_first=bool(b.first20high_in_I)))
 pd.DataFrame(pairs).to_csv(B/'EARLY_MISS_MATCHED_CONTROLS.csv',index=False)
 # Small understandable counterexamples, chosen after outcomes and never optimization inputs.
 examples=pd.concat([f.loc[f.group.eq('lost_large330')&f.first20high_in_I].sort_values(['day','sid']).head(3),f.loc[f.group.eq('lost_failed_only')&f.first20high_in_I].sort_values(['day','sid']).head(3)]);examples.to_csv(B/'EARLY_MISS_FRESH_BREAK_EXAMPLES.csv',index=False)
 dump('EARLY_MISS_COMPLETION.json',dict(status='COMPLETE_BOUNDED_EXPLANATION_ONLY',rows=len(f),cache_stock_files=f.sid.nunique(),matched_pairs=len(pairs),large_early_recovery_sufficient_count=int(f.loc[f.group.eq('lost_large330'),'first20high_in_I'].sum()),failed_only_also_restored=int(f.loc[f.group.eq('lost_failed_only'),'first20high_in_I'].sum()),seconds=time.time()-tick,no_new_full_ranking_or_account_run=True));print(pd.DataFrame(summary).to_string(index=False));print(examples[['group','day','sid','age','score','hold5','A_up','discount_score','ret20','ret60','new20high','first20high_in_I']].to_string(index=False));print((B/'EARLY_MISS_COMPLETION.json').read_text())
if __name__=='__main__':main()
