"""Read-only admission funnel and per-stock cash flow evidence."""
from pilot import *
from raw_review import CASES
def read(p):return json.loads(Path(p).read_text())
def main():
 meta=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol').to_dict('index');summary=[];events=[]
 for name in ['P0','P1','D1']:
  obj=read(O/f'results/{name}.json');fund={(r['sid'],r['signal_at']):r for r in obj['audit'] if r['kind']=='pilot_frozen_funding'};fills={(r['security_id'],r['signal_at']):r for r in obj['trades'] if r['side']=='buy'};reserves={(r['sid'],r['decision_at']):r for r in obj['audit'] if r['kind']=='reserve'};guards={(r['sid'],r['intent']['clock']['decision_at']) for r in obj['audit'] if r['kind']=='pilot_buy_rejected'}
  for r in obj['decisions']:
   for i in r['intents']:
    sid=i['sid'];key=(sid,r['at']);f=fund.get(key);fill=fills.get(key);reserved=key in reserves
    if fill:reason='filled'
    elif not f:reason='no_next_open_in_study'
    elif D(f['budget'])<=0:reason='cash_not_allocated'
    elif not reserved and not i['cap']:reason='full_2pct_budget_below_minimum'
    elif not reserved:reason='allocated_budget_below_minimum'
    elif key in guards:reason='open_protection_reject'
    else:reason='reserved_but_no_fill'
    events.append(dict(account=name,symbol=sid,name=meta[sid]['name'],signal=r['at'],kind=i['kind'],reason=reason,desired=float(i['budget']),allocated=float(f['budget']) if f else 0,raw_close=float(pd.read_parquet(SNAP/'facts'/f'{sid}.parquet').loc[r['at'][:10]].raw_close) if sid in CASES else None,pvr=i['score'],buy_shares=fill['shares'] if fill else 0))
  for sid in CASES:
   for year in [2024,2025,2026]:
    es=[e for e in events if e['account']==name and e['symbol']==sid and e['signal'][:4]==str(year)];summary.append(dict(account=name,symbol=sid,name=meta[sid]['name'],year=year,intents=len(es),**dict(collections.Counter(e['reason'] for e in es))))
 pd.DataFrame(events).to_csv(O/'analysis/admission-events.csv',index=False);pd.DataFrame(summary).fillna(0).to_csv(O/'analysis/named-admission-funnel.csv',index=False)
 print('Explained',len(events))
if __name__=='__main__':main()
