"""Matched-date summaries of frozen table; no new labels or rank changes."""
from analyze import O,read,save,mean,np,defaultdict
def main():
 rr=read(O/'ALL_INDUSTRY_DAYS.json');summary=[];daily=[];loo=[];mechanical=[]
 for case in ['2022Jan','2025Jul']:
  for family,col in [('M1','fresh_Q_pass'),('M2','C_requested_count')]:
   rs=[r for r in rr if r['case']==case and r[col]>0]
   mechanical.append(dict(case=case,family=family,industry_days=len(rs),positive_rank_improvement=sum(r['rank_improvement21']>0 for r in rs),rank_improved_but_own_price_nonpositive=sum(r['rank_improvement21']>0 and r['industry_absolute_price_change21_pct']<=0 for r in rs),B_promoted_own_price_nonpositive=sum(r[family+'_rank_group']=='B_promoted' and r['industry_absolute_price_change21_pct']<=0 for r in rs),improvement_tied_industry_days=sum(sum(v['day']==r['day'] and v['rank_improvement21']==r['rank_improvement21'] for v in rs)>1 for r in rs)))
   for h in ['21','63']:
    suffix=f'{family}_{h}_';zs=[r for r in rs if r[suffix+'label_n']];days=sorted({r['day'] for r in rs})
    def paired(rows):
     out=[]
     for d in days:
      B=[r for r in rows if r['day']==d and r[family+'_rank_group']=='B_promoted'];A=[r for r in rows if r['day']==d and r[family+'_rank_group']=='A_promoted']
      if not B or not A:continue
      out.append(dict(case=case,family=family,horizon=h,day=d,B_industries=len(B),A_industries=len(A),**{f'{g}_{field}':mean([r[suffix+field] for r in rowsg]) for g,rowsg in [('B',B),('A',A)] for field in ['return','MAE','MFE','tail_share']}))
     return out
    pp=paired(zs);daily+=pp
    summary.append(dict(case=case,family=family,horizon=h,common_days=len(pp),**{f'{g}_{field}':mean([p[f'{g}_{field}'] for p in pp]) for g in ['A','B'] for field in ['return','MAE','MFE','tail_share']},return_difference=mean([p['B_return']-p['A_return'] for p in pp]),B_better_days=sum(p['B_return']>p['A_return'] for p in pp),return_daily_difference_median=float(np.median([p['B_return']-p['A_return'] for p in pp])) if pp else None))
    if family=='M2':
     for sec in sorted({r['sector'] for r in zs}):
      p=paired([r for r in zs if r['sector']!=sec]);loo.append(dict(case=case,horizon=h,omitted_industry=next(r['industry'] for r in zs if r['sector']==sec),common_days=len(p),return_difference=mean([r['B_return']-r['A_return'] for r in p])))
 actual={}
 named=read(O/'NAMED_STOCK_CONTROLS.json')
 for case in ['2022Jan','2025Jul']:
  vals=defaultdict(float)
  for r in rr:
   if r['case']==case:vals[r['industry']]+=r['actual_C10_entry_contribution_to_month_end']
  positive=sum(max(0,v) for v in vals.values());best=max(vals,key=vals.get)
  actual[case]=dict(sum_all_entry_contributions=sum(vals.values()),positive_industry_net_sum=positive,largest_positive_industry=best,largest_positive_industry_net=vals[best],largest_positive_industry_share=vals[best]/positive if positive else None,all_industry_entry_contributions=dict(vals),named_stock_actual_contributions={sid:sum(float(z.get('net',z.get('total_contribution'))) for z in named['actual_original_C10_layers'][case] if z['sid']==sid) for sid in ['300199.SZ','002373.SZ','001267.SZ']})
 save('MATCHED_DATE_PROXY_SUMMARY.json',summary);save('MATCHED_DATE_PROXY_DAILY.json',daily);save('MATCHED_DATE_LEAVE_ONE_OUT.json',loo);save('RANK_CHANGE_ABSOLUTE_PRICE_AND_TIES.json',mechanical);save('ORIGINAL_C10_CONTRIBUTION_CONCENTRATION.json',actual)
 print('MATCHED',summary)
 print('MECHANICAL',mechanical)
 print('ACTUAL',[(k,{f:v for f,v in z.items() if f!='all_industry_entry_contributions'}) for k,z in actual.items()])
if __name__=='__main__':main()
