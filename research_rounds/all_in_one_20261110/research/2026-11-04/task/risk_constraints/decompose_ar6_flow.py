"""Read only actual flow + original trusted per-close floor, no engine imports."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip,argparse,hashlib
Z=D(0)
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);final=read(a.run/'FINAL.json.gz');trusted=read(a.run/'TRUSTED.json.gz')
    flows=[json.loads(line) for line in (a.run/'FLOW.jsonl').read_text().splitlines() if line]
    account=final['account'];buys={t['layer']:t for t in account['trades'] if t['side']=='buy'}
    splits=[c for c in account['native_callbacks'] if c.get('kind')=='native_split']
    byday={str(r['at'])[:10]:trusted[r['certificate']['trusted_id']]['snapshot'] for r in final['results']}
    rows=[];sums=defaultdict(lambda:Z)
    for f in flows:
        if f['phase']!='CLOSE':continue
        day=f['day'];s=byday[day];lots={z['id']:z for z in s['lots']};amount=defaultdict(lambda:Z)
        for r in f['resources']['rows']:
            if r['kind']!='lot':amount['pending_risk']+=D(r['risk']);continue
            z=lots[r['id']];buy=buys[r['id']];cost=D(buy['gross_cny'])/buy['shares']
            for c in splits:
                splitday=c['event'].split(':')[-1]
                if c['sid']==r['sid'] and buy['at'][:10]<splitday<=day:cost/=D(c['ratio'])
            q=D(z['qty']);mark=D(z['mark']);floor=D(z['floor'])
            assert q*mark==D(r['capital'])
            principal=q*max(Z,min(mark,cost)-floor);giveback=q*max(Z,mark-max(cost,floor));line=q*max(Z,mark-floor)
            assert abs(principal+giveback-line)<D('1e-16')
            extra=D(r['risk'])-line;assert extra>=D('-1e-16')
            amount['principal']+=principal;amount['giveback']+=giveback;amount['line']+=line;amount['lock_extra']+=extra
        for k in ('principal','giveback','line','lock_extra','pending_risk'):amount[k]+=Z
        amount['total_risk']=amount['principal']+amount['giveback']+amount['lock_extra']+amount['pending_risk']
        assert abs(amount['total_risk']-D(f['bridge']['resources']['risk']))<D('1e-16')
        for k,v in amount.items():sums[k]+=v
        rows.append(dict(day=day,**dict(amount)))
    result=dict(close_count=len(rows),first=rows[0]['day'],last=rows[-1]['day'],equal_close_risk_yuan_sums=dict(sums),
        principal_share_of_line=sums['principal']/sums['line'],giveback_share_of_line=sums['giveback']/sums['line'],
        lock_extra_share_of_total=sums['lock_extra']/sums['total_risk'],financial_events=0,
        clock='original trusted post-stock-protection same-close raw floor; actual final-close risk incl new execution locks; not projected donor releases',
        cost='actual gross buy fill unit cost, adjusted by actual native integer split events through this close; buy fees excluded from split reference',
        sources={n:hashlib.sha256((a.run/n).read_bytes()).hexdigest() for n in ['FINAL.json.gz','TRUSTED.json.gz','FLOW.jsonl']})
    (a.out/'SUMMARY.json').write_text(json.dumps(result,indent=2,default=str)+'\n');(a.out/'DAILY.json').write_text(json.dumps(rows,indent=2,default=str)+'\n')
    print(json.dumps(result,default=str))
if __name__=='__main__':main()
