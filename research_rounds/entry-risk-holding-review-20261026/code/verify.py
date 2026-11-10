from pathlib import Path
from decimal import Decimal
import datetime, hashlib, json, math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
SEC=ROOT/'research_rounds/sector-ix-i-20261026'
OLD=ROOT/'research_rounds/rs-h1-execution-20261025'
IX=ROOT/'research_rounds/ix-a-share-entry-20261025'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    out=HERE/'verification-v1';out.mkdir(exist_ok=False)
    frozen=read(HERE/'freeze.json')
    for path,value in frozen['files'].items():assert sha(ROOT/path)==value,path
    f=pd.read_csv(HERE/'prepared-v2/funded.csv');c=pd.read_csv(SEC/'analysis-v2/campaigns.csv')
    assert len(f)==len(c)==3646
    assert c.loc[(c.sell_fills>0)&~c.closed].empty, 'future final-closed label would affect feedback eligibility'
    source_keys=set(zip(c.account,c.symbol,c.entry_at));assert source_keys==set(zip(f.account,f.symbol,f.entry_at))
    rows=[];risk_checks=0;feedback_checks=0
    manifest={s['series_id']:s for s in read(OLD/'prepared-v2/manifest.json')['series']}
    curves=pd.read_csv(SEC/'analysis-v2/curves.csv'); nav={(g+'_'+p+'__S1_base',str(d)):float(n) for g,p,d,n in curves[['group','policy','date','nav']].itertuples(index=False,name=None)}
    for aid,g in f.groupby('account'):
        obj=read(SEC/'accounts-v2'/f'{aid}.json')
        res={x['order_id']:x for x in obj['audit_log'] if x['kind']=='reserve'}
        buys={(x['receipt']['security_id'],x['receipt']['at']):x for x in obj['audit_log'] if x['kind']=='fill' and x['receipt']['side']=='buy'}
        # Rebuild feedback from source cash values; no diagnostic feedback routine is imported.
        prior=[]
        for x in c[c.account.eq(aid)].to_dict('records'):
            if x['sell_fills']==1 and pd.notna(x['exit_at']) and x['final_shares']==0:
                value=sum(Decimal(str(x[k]))*sign for k,sign in [('sell_gross',1),('sell_fees',-1),('buy_gross',-1),('buy_fees',-1)])
                prior.append((pd.Timestamp(x['exit_at']),x['symbol'],value))
        prior.sort(key=lambda x:(x[0],x[1]))
        for x in g.to_dict('records'):
            b=buys[x['symbol'],x['entry_at']];r=res[b['order_id']];day=pd.Timestamp(r['decision_at']).tz_localize(None).normalize();entry=pd.Timestamp(x['entry_at']).tz_localize(None).normalize()
            assert str(pd.Timestamp(r['decision_at']))==x['decision_at'];assert day<entry
            ss=pd.read_parquet(IX/'signals'/f"{x['symbol']}.parquet",columns=['e0_floor','close'])
            sg=pd.read_parquet(OLD/'prepared-v2'/manifest[x['symbol']]['files']['signal']['path'],columns=['adjustment_factor'])
            floor=float(ss.loc[day,'e0_floor'])/float(sg.loc[entry,'adjustment_factor']); px=float(b['price']); shares=int(b['receipt']['shares']);nv=nav[aid,str(day.date())]
            if float(b['raw_open'])<=floor:assert x['gap_below_support']
            else:
                expected=float((Decimal(str(px))-Decimal(str(floor)))*Decimal(shares)/Decimal(str(nv)))
                assert abs(expected-x['initial_risk_nav'])<2e-14
            assert abs((px-floor)/px-x['support_distance'])<2e-14;risk_checks+=1
            pp=[v for v in prior if v[0]<pd.Timestamp(x['decision_at'])][-5:]
            n=len(pp);loss=sum(v[2]<0 for v in pp);bucket='insufficient' if n<5 else '4plus_losses' if loss>=4 else 'other'
            assert (n,loss,bucket)==(x['prior_closed_n'],x['prior_price_losses'],x['feedback_bucket'])
            feedback_checks+=1
        eligible=g[g.entry_at.str[:10].le('2023-12-29')].sort_values('entry_at')
        for _,x in eligible.iloc[[0,-1]].iterrows():
            sid=x.symbol;day=pd.Timestamp(x.decision_day);entry=pd.Timestamp(x.entry_at).tz_localize(None).normalize()
            full=pd.read_parquet(IX/'signals'/f'{sid}.parquet')
            signal_path=out/f'{aid}-{sid}-{str(day.date())}-signal-prefix.parquet'
            full.loc[:'2023-12-29'].to_parquet(signal_path)
            prefix=pd.read_parquet(signal_path);h=prefix.loc[:day];r=h.iloc[-1]
            sf=pd.read_parquet(OLD/'prepared-v2'/manifest[sid]['files']['signal']['path'])
            raw_path=out/f'{aid}-{sid}-{str(day.date())}-source-prefix.parquet'
            sf.loc[:'2023-12-29'].to_parquet(raw_path);sg=pd.read_parquet(raw_path)
            ep=x.actual_entry_price*float(sg.loc[entry,'adjustment_factor'])
            d=(ep-float(r.e0_floor))/ep
            assert abs(d-x.support_distance)<2e-14
            sub=h[h.segment_id.eq(r.segment_id)];j=len(sub)-1;trs=[]
            for k in range(j-14,j):
                z=sub.iloc[k];prev=float(sub.iloc[k-1].close)
                trs.append(max((float(z.high)-float(z.low))/prev,abs(float(z.high)/prev-1),abs(float(z.low)/prev-1)))
            tr=sum(trs)/14;assert abs(tr-x.lag_tr14)<2e-14
            assert abs(d/tr-x.distance_tr)<2e-12
            assert int(sub.e0_entered.sum())==x.e0_sequence
            rows.append(dict(account=aid,symbol=sid,decision_day=x.decision_day,entry_day=str(entry.date()),support_distance=d,lag_tr14=tr,passed=True))
    p=pd.read_parquet(HERE/'prepared-v2/opportunities.parquet');first={}
    for x in sorted(p.to_dict('records'),key=lambda r:(r['event_day'],r['symbol'])):
        key=(x['group'],x['symbol'],x['segment'],x['e0_sequence']);first.setdefault(key,x['event_day'])
    d=pd.read_parquet(HERE/'results-v1/first-e0-opportunities.parquet')
    assert len(first)==len(d)==4895
    for x in d.to_dict('records'):assert first[x['group'],x['symbol'],x['segment'],x['e0_sequence']]==x['event_day']
    result=dict(passed=True,recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_hash_checks=len(frozen['files']),risk_and_clock_checks=risk_checks,strict_prior_cash_feedback_checks=feedback_checks,physical_feature_prefix_checks=rows,source_safe_first_e0_events=len(first),no_new_economic_accounts=True,independent_code_sha256=sha(__file__))
    (out/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='physical_feature_prefix_checks'});print('physical_feature_prefix_checks',len(rows))

if __name__=='__main__':main()
