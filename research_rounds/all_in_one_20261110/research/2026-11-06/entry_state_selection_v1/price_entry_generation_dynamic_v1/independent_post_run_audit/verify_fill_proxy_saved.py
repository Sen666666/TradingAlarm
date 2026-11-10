"""Posterior saved-fill source check only. Does not alter decisions or rerun economics."""
import argparse,json,csv,hashlib,math
from collections import defaultdict,Counter
from pathlib import Path
from decimal import Decimal as N
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');D=R/'price_entry_generation_dynamic_v1';J=R/'independent_channel_joint_economic_v1';OUT=D/'independent_post_run_audit'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open() as f:return list(csv.DictReader(f))
def main(w):
    m={x['symbol']:x for x in read(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))}
    roster={r['sid'] for r in rows(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')};assert len(roster)==1709
    finance=read(OUT/('FINANCIAL_'+w+'_RAW.json'));fm={(r['arm'],r['round_id']):r for r in finance['rounds']}
    acts=[];rd={};violations=[];used={}
    for arm,p in [('baseline',J/('economic_'+w)),('joint',D/('gate_'+w))]:
        for r in rows(p/'joint/ROUNDS.csv'):
            assert r['sid'] in roster
            rd[arm,r['round_id']]=r
            if r.get('actual_ack')!='NOT_PROVIDED' or r.get('actual_fill')!='NOT_PROVIDED':violations.append(['UNEXPECTED_ACTUAL_CLAIM',arm,r['round_id']])
            if r['signal_day'] and not (('2022-01-01'<=r['signal_day']<='2022-12-31') if w=='2022' else ('2024-09-01'<=r['signal_day']<='2024-12-31')):violations.append(['CREATION_WINDOW',arm,r['round_id'],r['signal_day']])
        for a in rows(p/'joint/ACTIONS.csv'):acts.append(dict(a,comparison_arm=arm))
    bysid=defaultdict(list)
    for a in acts:bysid[a['sid']].append(a)
    dep=defaultdict(list)
    for sid,aa in bysid.items():
        paths=[(p,h) for p,h in m[sid]['source_sha256'].items() if p.endswith('/signal.parquet')];assert len(paths)==1
        p,h=paths[0];p=Path(p);assert sha(p)==h;used[str(p)]=h
        fr=pd.read_parquet(p,columns=['raw_open','raw_high','raw_low','raw_close'])
        for a in aa:
            dt=pd.Timestamp(a['day']);z=fr.loc[dt];buy=a['side'].startswith('buy');expected=N(str(z.raw_open))*(N('1.0005') if buy else N('.9995'))
            if not math.isclose(float(expected),float(a['price']),rel_tol=1e-12,abs_tol=1e-9):violations.append(['SLIPPAGE_PROXY',a,float(expected)])
            vals=[z.raw_open,z.raw_high,z.raw_low,z.raw_close]
            known=all(pd.notna(v) and math.isfinite(float(v)) for v in vals)
            one=known and len({float(v) for v in vals})==1
            hl=known and float(z.raw_high)==float(z.raw_low)
            if one or hl or not known:dep[a['comparison_arm'],a['round_id']].append(dict(day=a['day'],side=a['side'],q=a['q'],one_price_ohlc=bool(one),one_price_hl=bool(hl),ohlc_known=known))
    summary=[]
    for arm in ['baseline','joint']:
        rs=[r for (ar,rid),r in fm.items() if ar==arm and r['entered'] and r['financial_covered'] and not r['unknown'] and r['full_closed'] is not None]
        depended=[r for r in rs if any(a['one_price_ohlc'] for a in dep[arm,r['round_id']])]
        missing=[r for r in rs if any(not a['ohlc_known'] for a in dep[arm,r['round_id']])]
        summary.append(dict(arm=arm,all_fill_records=sum(a['comparison_arm']==arm for a in acts),financial_covered_closed=len(rs),closed_net=sum(r['full_closed'] for r in rs),one_price_dependent_closed=len(depended),one_price_dependent_net=sum(r['full_closed'] for r in depended),unannotated_closed=len(missing),descriptive_other_closed_net=sum(r['full_closed'] for r in rs if r not in depended and r not in missing),closed_losses_below_minus3000=sum(r['full_closed'] < -3000 for r in rs)))
    out=dict(window=w,status='PASS_POSTERIOR_EXECUTION_PROXY_CHECK' if not violations else 'FAIL',economic_runs=0,all_action_rows=len(acts),signal_source_count=len(used),source_sha256=used,summary=summary,violations=violations,dependent_rounds=[dict(arm=arm,round_id=rid,actions=aa) for (arm,rid),aa in dep.items() if aa],interpretation='OHLC one-price dependence is posterior and not used to accept or reject OPEN fills. These are assumed full-fill proxies, actual ACK/fill NOT_PROVIDED; no rerun excluding cases.')
    p=OUT/('FILL_PROXY_'+w+'.json')
    with p.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:out[k] for k in ['window','status','all_action_rows','signal_source_count','summary','violations']},ensure_ascii=False));print(p,sha(p))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--window',required=True);main(ap.parse_args().window)
