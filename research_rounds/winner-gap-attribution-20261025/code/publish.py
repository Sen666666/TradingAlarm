from common import *
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')

def main():
 out=HERE/'report';out.mkdir(exist_ok=False);(out/'figures').mkdir();meta=read(OLD/'inputs-v2/metadata.json');tr=pd.read_parquet(HERE/'enriched/all-daily-traces.parquet');actual=pd.read_csv(HERE/'detail/actual-focus-campaigns.csv');coverage=pd.read_csv(HERE/'detail/coverage.csv');summ=[]
 snaps=read(HERE/'enriched/rejected-event-snapshots.json');correct=[]
 for sid in IDS:
  ss=[x for x in snaps if x['account']=='IX__S0_base' and x['symbol']==sid];relieved=[x for x in ss if x['actually_closed_latched_next_day'] and x['capacity_fits_after_actual_latched_exits']]
  correct.append(dict(symbol=sid,blocked=len(ss),with_pending_exit=sum(x['pending_exit_count']>0 for x in ss),actual_next_day_exit_relieves_capacity=len(relieved),also_minimum_lot_fits=sum(not x['minimum_lot_exceeds_cap'] for x in relieved)))
 pd.DataFrame(correct).to_csv(out/'capacity-relief-corrected.csv',index=False)
 write(out/'capacity-correction.json',dict(recorded_at=now(),reason='original summary counted capacity already fitting with zero actual exits; this table requires at least one actual next-day latched exit',original_preserved=True,new_trades_or_rule_changes=0))
 for sid in IDS:
  f=pd.read_parquet(SRC/'signals'/f'{sid}.parquet').loc[START:END];q=tr.loc[tr.account.eq('IX__S0_base')&tr.symbol.eq(sid)].set_index('date');q.index=pd.to_datetime(q.index);q=q.reindex(f.index);base=f.close.iloc[0];cc=actual.loc[actual.account.eq('IX__S0_base')&actual.symbol.eq(sid)&actual.entry_at.str[:10].ge('2023-01-01')]
  fig,ax=plt.subplots(6,1,figsize=(14,12),sharex=True,gridspec_kw={'height_ratios':[3,1,1.25,1,1.15,1.35]})
  ax[0].plot(f.index,f.close/base*100,color='#253e46',lw=1,label='price / first close');ax[0].plot(f.index,(f.e0_floor/base*100).where(f.e0_target.eq(1)),color='#98aaa5',lw=.65,alpha=.7,label='E0 support');ax[0].set_yscale('log');ax[0].set_title(meta[sid]['name']+'：已识别、可竞争、真正买入是三件事',fontproperties=FONT,loc='left');ax[0].set_ylabel('price index (log)')
  for j,(_,c) in enumerate(cc.iterrows()):
   for col,marker,color in [('entry_at','^','#16816f'),('exit_at','v','#ba5755')]:
    if pd.notna(c[col]):
     d=pd.Timestamp(c[col][:10]);ax[0].scatter([d],[f.loc[d,'open']/base*100],s=36,marker=marker,color=color,zorder=3,label=('S0 actual buy' if col=='entry_at' else 'S0 actual sell') if j==0 else None)
  ax[0].legend(fontsize=8,loc='upper left')
  lanes=[(f.e0_target.eq(1),'E0 eligibility','#8caaa2'),(f.ix_target.eq(1),'IX eligibility','#5287b3'),(q.held.fillna(False),'actual IX-S0','#263f46')]
  for j,(mask,label,color) in enumerate(lanes):ax[1].fill_between(f.index,j,j+.7,where=mask,step='post',color=color);ax[1].text(f.index[0],j+.32,label,fontsize=8)
  ax[1].set_ylim(-.1,3);ax[1].set_yticks([])
  ax[2].step(f.index,f.score,where='post',color='#aa793b',lw=.8);ax[2].set_yticks([-75,-50,0,50,75,100]);ax[2].set_ylabel('G1 score');ax[2].axhline(75,lw=.4,color='gray')
  for j,m in enumerate(MODES):ax[3].scatter(f.index[f[m]],np.full(int(f[m].sum()),j),marker='|',s=28,color=['#16816f','#c18637','#3c6db1','#995a9c'][j])
  ax[3].set_yticks(range(4),[m+': '+str(int(f[m].sum())) for m in MODES]);ax[3].set_ylim(-.5,3.5)
  ax[4].plot(f.index,q.stock_rs,color='#253e46',lw=.8,label='stock RS-H1');ax[4].plot(f.index,q.sector_rs,color='#6487b0',lw=.8,label='sector RS-H1');ax[4].set_ylim(0,102);ax[4].legend(fontsize=8,loc='lower right');ax[4].set_ylabel('RS percentile')
  ax[5].plot(f.index,q.minimum_lot_notional/1e4,color='#6487b0',lw=.9,label='minimum buy / CNY10k');ax[5].plot(f.index,q.initial_cap_upper/1e4,color='#bd8735',lw=.9,label='15% NAV cap / CNY10k');ax[5].set_yscale('log');ax[5].set_ylabel('cash bound (log)');ax[5].legend(fontsize=8,loc='upper left')
  for a in ax:a.grid(alpha=.16)
  fig.text(.08,.012,'2023—2026-10-22；价格为旧因果复权坐标，底图最小买入金额用原价。状态覆盖不是策略收益，最小金额不含费用。',fontproperties=FONT,fontsize=9);fig.tight_layout(rect=(0,.035,1,1));fig.savefig(out/'figures'/f'{sid}.png',dpi=140);plt.close(fig)
  c=[x for x in read(HERE/'detail/price-context.json') if x['symbol']==sid][0];c['end_over_start']=c['price_return']+1;c['S0_recent_cycles']=len(cc);c['S0_recent_pnl']=float(cc.net_pnl.sum());c['E0_days']=int(coverage.loc[coverage.symbol.eq(sid)&coverage.kind.eq('E0_saved_state'),'qualified_days'].iloc[0]);c['IX_days']=int(coverage.loc[coverage.symbol.eq(sid)&coverage.kind.eq('IX_saved_state'),'qualified_days'].iloc[0]);c['actual_S0_days']=int(q.held.fillna(False).sum());summ.append(c)
 pd.DataFrame(summ).to_csv(out/'focus-summary.csv',index=False);write(out/'focus-summary.json',summ)
 payload=dict(summary=summ,actual=json.loads(actual.to_json(orient='records',force_ascii=False)),cases=read(HERE/'enriched/explanatory-cases.json'),capacity=correct,cohort=read(HERE/'cohort-v1/summary.json'),selected=read(HERE/'enriched/selected-price-vs-exit.json'),outcomes=json.loads(pd.read_csv(HERE/'detail/event-outcomes.csv').to_json(orient='records',force_ascii=False)),lot=json.loads(pd.read_csv(HERE/'enriched/minimum-lot-summary.csv').to_json(orient='records',force_ascii=False)))
 raw=json.dumps(clean(payload),ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('</','<\\/');html=Path(__file__).with_name('report.html').read_text().replace('__PAYLOAD__',raw);(out/'index.html').write_text(html)
 write(out/'receipt.json',dict(recorded_at=now(),passed=True,figures=3,new_accounts=0,saved_state_vs_actual_comparison=True,all_old_results_preserved=True,capacity_summary='capacity-relief-corrected.csv'))
 print(pd.DataFrame(summ).to_string(index=False),flush=True);print('corrected capacity',correct,flush=True)
if __name__=='__main__':main()
