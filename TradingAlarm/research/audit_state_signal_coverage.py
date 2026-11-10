"""Map dated state coverage onto fixed signals; select collection priority without future returns."""
import json
from pathlib import Path
import pandas as pd
from stock_entry_diagnostic import select
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/stock-data-audit'
def main():
    calendar=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values()
    nextdate=dict(zip(calendar[:-1],calendar[1:]))
    candidates=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet')
    candidates=candidates[candidates.active20.eq(20)]
    selections={'low_atr':select(candidates,'atr_fraction'),'rs':select(candidates,'rs_order')}
    states={};windows=set()
    for p in sorted((ROOT/'data/stock-state-windows').glob('*.json')):
        data=json.loads(p.read_text());symbol=data['symbol'];windows.add((symbol,data['year']))
        for r in data['rows']:states[(symbol,r['date'])]=r
    rows=[]
    for name,f in selections.items():
        for r in f.itertuples():
            execution=nextdate.get(r.date)
            if execution is None:continue
            s=states.get((r.symbol,str(execution.date())))
            rows.append(dict(strategy=name,symbol=r.symbol,signal_date=str(r.date.date()),execution_date=str(execution.date()),year=execution.year,state_available=s is not None,trading=(s['tradestatus']=='1') if s else None,is_st=(s['isST']=='1') if s else None))
    table=pd.DataFrame(rows);table.to_csv(OUT/'state-signal-coverage.csv',index=False)
    report=[]
    for name,f in table.groupby('strategy'):
        covered=f[f.state_available]
        report.append(dict(strategy=name,signals=len(f),covered=len(covered),suspended=int(covered.trading.eq(False).sum()),st=int(covered.is_st.eq(True).sum()),execution_ready=False))
    missing=table[~table.state_available].groupby(['symbol','year']).size().rename('signal_count').reset_index().sort_values(['signal_count','symbol','year'],ascending=[False,True,True])
    missing['window_already_cached']=[(s,y) in windows for s,y in zip(missing.symbol,missing.year)]
    missing.to_csv(OUT/'state-window-priority.csv',index=False)
    (OUT/'state-signal-coverage.json').write_text(json.dumps(dict(records=report,priority='Descending count of fixed historical signals, ties by code/year; no forward returns used',limitation='Trading/ST only; unknown price limits and corporate actions still block executable returns'),indent=2))
    print(report);print(missing.head(10).to_string(index=False))
if __name__=='__main__':main()
