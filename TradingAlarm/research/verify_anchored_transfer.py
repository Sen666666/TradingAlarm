"""Verify original controls, frozen sources, and summarize all fixed candidates."""
import json,hashlib
from pathlib import Path
import pandas as pd
OUT=Path('results/strength-anchored-transfer485')
def main():
    protocol=json.loads((OUT/'protocol.json').read_text())
    for name,digest in protocol['source_sha256'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
    old=pd.read_parquet('results/trend-strength-transfer485/episodes.parquet');new=pd.read_parquet(OUT/'episodes.parquet')
    def control(f):return f.loc[f.strategy.eq('adaptive_geometry_price_volume')].sort_values(['symbol','delay','cutoff','entry_date']).reset_index(drop=True)
    pd.testing.assert_frame_equal(control(old),control(new),check_exact=True)
    sleeve=json.loads((OUT/'sleeve-report.json').read_text())['rows'];tails=json.loads((OUT/'tail-economics.json').read_text())['reports'];summ=json.loads((OUT/'summary.json').read_text());rows=[]
    for name in protocol['strategies']:
        r=next(r for r in sleeve if r['strategy']==name and r['allocation']=='equal_capital' and r['cutoff']=='2026-10-16' and r['scenario']=='base' and r['cost']==15 and r['terminal']=='last_mark')
        t=next(r for r in tails if r['strategy']==name and r['allocation']=='equal_capital')
        s=next(r for r in summ if r['strategy']==name and r['cutoff']=='2026-10-16' and r['cohort']=='all' and r['delay']==0 and r['cost']==15)
        row={'strategy':name,'full_return':r['equal_initial_sleeve_return'],'year2026':r['year2026_carry_return'],'tail':t,'win_rate':s['closed_win_rate'],'payoff':s['payoff']};rows.append(row)
        print(name,'full',row['full_return'],'2026',row['year2026'],'win',row['win_rate'],'payoff',row['payoff'],'ordinary<30',t['thresholds'][0]['ordinary_pnl_fraction'],'tail>=30',t['thresholds'][0]['tail_pnl_fraction'])
    result={'exact_original_control_rows':len(control(new)),'frozen_sources_verified':len(protocol['source_sha256']),'rows':rows,'limits':'Fixed isolated fractional adjusted-price sleeves, not actual account returns or drawdown. Previously reviewed symbols/dates, not unseen validation. Tail categories hindsight.'}
    (OUT/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
