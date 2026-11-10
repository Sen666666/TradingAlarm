"""Reusable HK episode attribution, including retained in-kind ownership."""
import argparse,json
import pandas as pd
from build_stock_features import ROOT
from hk_in_kind_campaign import load_assets
from monthly_hk_episode_audit import audit,summary


def main(output):
    out=ROOT/'results'/output;assets,_=load_assets();reports=[]
    for r in json.loads((out/'results.json').read_text()):
        if r['group']!='hk7':continue
        case=r['case'];p=pd.read_parquet(out/f'{case}-path.parquet')
        episodes,error=audit(assets,p,json.loads((out/f'{case}-orders.json').read_text()),20 if r['scenario']=='cost2' else 10,allow_claims=True)
        report=dict(case=case,**summary(episodes),max_daily_error=error,parent_closed_with_remaining_claims=sum(bool(e['exit_date']) and e.get('nontradable_claim_value',0)>0 for e in episodes))
        (out/f'{case}-episodes.json').write_text(json.dumps(episodes,indent=2));reports.append(report)
        if r['scenario']=='base':print({k:report[k] for k in ('case','closed_count','closed_win_rate','average_win','average_loss','ordinary_all_bottom90','parent_closed_with_remaining_claims')})
    (out/'episode-attribution.json').write_text(json.dumps(dict(results=reports,meaning='Closed means parent strategy position closed;any distributed shares remain marked within owningepisode and are not realizedcash. All episode PNL sum toaccountNAV daily. Top10percent removal hindsight only.'),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);main(parser.parse_args().output)
