from pathlib import Path
import sys,json,gzip,collections
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'research_rounds/tech-finite-compound-20261026';HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'code'));from common import *
ss=pd.read_csv(BASE/'analysis/stocks.csv');c=pd.read_csv(BASE/'analysis/campaigns.csv');summary=pd.read_csv(BASE/'analysis/summary.csv')
a=ss[ss.account.eq('I__S0_base')].set_index('symbol');b=ss[ss.account.eq('I__S0_delay1')].set_index('symbol');x=a[['name','net_profit']].rename(columns={'net_profit':'base'}).join(b[['net_profit']].rename(columns={'net_profit':'delay'}),how='outer');x.name=x.name.fillna(b.name);x[['base','delay']]=x[['base','delay']].fillna(0);x['gap']=x.base-x.delay;x=x.sort_values('gap',ascending=False);x.to_csv(HERE/'old-I-stock-gaps.csv')
for aid in ['I__S0_base','I__S0_delay1']:
 obj=json.loads((BASE/'accounts-v2'/f'{aid}.json').read_text());logs=obj['audit_log'];counts=collections.Counter(r['kind'] for r in logs);print(aid,dict(counts));print(summary[summary.account.eq(aid)].to_dict('records'))
print(x.head(12).round(2).to_string());print(x.tail(5).round(2).to_string())
