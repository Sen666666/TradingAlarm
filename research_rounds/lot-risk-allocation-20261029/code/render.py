"""Render existing audited results only; creates no account paths."""
import analyze as Q
from study import *
def main():
 (O/'charts').mkdir(exist_ok=False);ds=Q.rows(O/'results/daily.jsonl.gz');df=pd.read_csv(O/'analysis/curves.csv');curves={}
 for name in ['P0','P1','L0','L1']:
  f=df[df.account.eq(name)];curves[name]=(pd.DatetimeIndex(f.date),f.nav.to_numpy(),f.market_value.to_numpy(),f.drawdown.to_numpy())
 obj={name:Q.load(O/f'results/{name}.json') for name in curves};meta=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol').to_dict('index');facts={s:pd.read_parquet(SNAP/'facts'/f'{s}.parquet').loc['2024-01-02':'2026-10-27'] for s in CASES}
 Q.plot(O/'analysis',curves,obj,{},ds,meta,facts,[])
 print('Rendered audited curves and 9 stock paths')
if __name__=='__main__':main()
