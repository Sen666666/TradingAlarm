from cp_common import *
def main():
 root=O/'DRUG';sid='688166.SH';obj=read(root/'accounts-v2/MCP__S0_base.json');c=pd.read_csv(root/'analysis/campaigns.csv');c=c[c.policy.isin(['SAMT','MCP'])&c.scenario.eq('base')&c.symbol.eq(sid)&c.entry_at.str.startswith('2025-05-09')]
 f=pd.read_parquet(PREPS['DRUG']/'facts'/f'{sid}.parquet');g=pd.read_parquet(SA/'signals/DRUG'/f'{sid}.parquet');blocked=[]
 for d in rows(root/'accounts-v2/decisions.jsonl.gz'):
  day=d['at'][:10]
  if d['account']!='MCP__S0_base' or not '2025-06-27'<=day<'2025-09-01' or sid not in d['eligible']:continue
  assert f.loc[day,'i_buy'] and g.loc[day,'strict_target'] and sid not in d['accepted'] and len(d['occupancy'])==6
  blocked.append(dict(date=day,accepted=d['accepted'],post_decision_occupancy=[p['security_id'] for p in d['occupancy']]))
 onward=[r for r in obj['fills'] if r['side']=='buy' and '2025-06-27'<r['at'][:10]<'2025-09-01']
 save(O/'borui-evidence.json',dict(same_entry_cycles=json.loads(c.to_json(orient='records')),later_qualified_unaccepted_stock_days=len(blocked),details=blocked,all_account_buys_during_release_interval=onward,caveat='7/11先接纳更高优先级002773后满六席，之后六席保持。为收盘接纳后资源状态；没有把同区间全部买单归因为某一笔释放的现金。'))
if __name__=='__main__':main()
