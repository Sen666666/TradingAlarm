"""Post-result descriptive attribution only; no new economic run."""
from evaluate import *

def main():
 snap=Path(read(O/'input.json')['snapshot']['path']);meta=pd.read_csv(C.DESIGN/'proposed-pool.csv').set_index('symbol');h=dict(np.load(snap/'h1.npz'));dates=pd.DatetimeIndex(h['dates']);col={str(s):j for j,s in enumerate(h['symbols'])}
 scores={s:pd.read_parquet(O/'scores'/f'{s}.parquet') for s in meta.index}
 unavailable=[]
 for sid in meta.index:
  f=pd.read_parquet(snap/'facts'/f'{sid}.parquet').loc['2024':];z=scores[sid].score.reindex(f.index);rs=pd.Series(h['score'][:,col[sid]],index=dates).reindex(f.index)
  blocked=f.i_buy.astype(bool)&f.i_target.astype(bool)&f.g_ready.astype(bool)&f.g_grade.ge(2)&z.isna()&rs.notna()
  for day in f.index[blocked]:unavailable.append({'symbol':sid,'name':str(meta.loc[sid,'name']),'date':str(day.date()),'reason':'原I事件具备但PVR85观察尚未准备或金额无效；尚未叠加行业/账户/容量'})
 pd.DataFrame(unavailable).to_csv(O/'unready-I-events.csv',index=False)
 scenarios=['base','cost2','delay1'];trace=[];state={};selection={};daily={}
 for v in ['RS','PVR']:
  selection[v]={(r['account'],r['at'][:10]):r for r in rows(O/v/'accounts-v2/decisions.jsonl.gz')};daily[v]={(r['account'],r['at'][:10]):r for r in rows(O/v/'accounts-v2/daily.jsonl.gz')}
  for sc in scenarios:
   ob=read(O/v/'accounts-v2'/f'I__S0_{sc}.json')
   state[v,sc]={r['at'][:10]:r for r in ob['audit_log'] if r['kind']=='risk_checkpoint'}
 for day,ids in [('2025-06-27',['300502.SZ']),('2025-10-20',['688498.SH','688048.SH'])]:
  for sid in ids:
   for v in ['RS','PVR']:
    d=selection[v]['I__S0_base',day];a=daily[v]['I__S0_base',day];pos=a['positions'];sec=meta.loc[sid,'sector_id'];held_same=[s for s in pos if meta.loc[s,'sector_id']==sec]
    trace.append({'version':v,'date':day,'symbol':sid,'name':meta.loc[sid,'name'],'RS':float(h['score'][dates.get_indexer([day])[0],col[sid]]),'PVR':float(scores[sid].loc[day,'score']),'eligible':sid in d['eligible'],'accepted':sid in d['accepted'],'account_on':state[v,'base'][day]['on'],'held_count':len(pos),'held_same_sector':'|'.join(held_same),'held_names':'|'.join(str(meta.loc[s,'name']) for s in pos),'holding_rule':'分数下降不退出，原E0结构持有'} )
 pd.DataFrame(trace).to_csv(O/'winner-opportunity-trace.csv',index=False)
 stages=pd.read_csv(O/'stages.csv');annual=pd.read_csv(O/'annual.csv');summary=pd.read_csv(O/'summary.csv');attr=pd.read_csv(O/'stock-attribution.csv')
 first=pd.read_csv(O/'selection-differences.csv').query('account=="I__S0_base" and same_accepts==False').iloc[0].to_dict()
 totals={}
 for sc in scenarios:
  a=summary[(summary.version=='RS')&(summary.scenario==sc)].iloc[0];b=summary[(summary.version=='PVR')&(summary.scenario==sc)].iloc[0];s=attr[attr.scenario==sc]
  assert abs(float(s.PVR_minus_RS.sum())-float(b.net_profit-a.net_profit))<1e-7
  totals[sc]={'profit_delta':float(b.net_profit-a.net_profit),'tail_profit_delta':float(b.tail_profit-a.tail_profit),'ordinary_profit_delta':float(b.ordinary_profit-a.ordinary_profit),'first_divergence_initial_sort':first if sc=='base' else None}
 result={'unready_original_I_event_days':len(unavailable),'unready_stocks':len({r['symbol'] for r in unavailable}),'winner_traces':trace,'reconciled_profit_difference':totals,'post_result_only':True,'economic_runs':0,'economic_rule_changes':0}
 save(O/'attribution.json',result)
 print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
