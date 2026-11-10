from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict
import json,hashlib,csv

HERE=Path(__file__).resolve().parent
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0)
getcontext().prec=80
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,x):
    p=HERE/name
    if p.exists(): raise FileExistsError(p)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
sources={}
datasets=[]
for sub,suffix in [('baseline_readonly',''),('analysis','_R0')]:
    p=OLD/'g-s-C-R0-continuous-january-v1-20261102'/sub/'ALL_LAYERS.json'
    sources[str(p)]=digest(p)
    for cell,ll in json.loads(p.read_text()).items():
        datasets.append(('2022Jan',cell+suffix,ll,str(p)))
for cell in ['C10','C20','C10_R0','C20_R0']:
    p=OLD/'g-s-C-August-continuation-v1-20261102/analysis'/f'{cell}-LAYERS.json'
    sources[str(p)]=digest(p)
    datasets.append(('2025JulAug',cell,json.loads(p.read_text()),str(p)))

rows=[];details=[];groups=[];reason_groups=[]
for period,cell,ll,source in datasets:
    assert len({x['layer'] for x in ll})==len(ll)
    closed=[x for x in ll if x['remaining_qty']==0]
    opened=[x for x in ll if x['remaining_qty']!=0]
    negative=[x for x in closed if D(x['total_contribution'])<0]
    positive=[x for x in closed if D(x['total_contribution'])>0]
    loss=-sum((D(x['total_contribution']) for x in negative),Z)
    top=sorted(negative,key=lambda x:D(x['total_contribution']))
    gross=sum((D(x['buy_gross']) for x in ll),Z)
    r=dict(period=period,cell=cell,layers=len(ll),closed=len(closed),open=len(opened),negative_closed=len(negative),positive_closed=len(positive),zero_closed=len(closed)-len(negative)-len(positive),buy_gross=gross,negative_closed_amount=loss,positive_closed_amount=sum((D(x['total_contribution']) for x in positive),Z),open_layer_contribution=sum((D(x['total_contribution']) for x in opened),Z),all_contribution=sum((D(x['total_contribution']) for x in ll),Z),closed_negative_to_all_buy_gross_pct=100*loss/gross,largest_5_negative_share_pct=-100*sum((D(x['total_contribution']) for x in top[:5]),Z)/loss,worst_closed_return_pct=min(100*D(x['total_contribution'])/D(x['buy_cost']) for x in closed),tail_closed=sum(D(x['total_contribution'])>=D('.3')*D(x['buy_cost']) for x in closed))
    for level in [10,20,30]:
        severe=[x for x in closed if D(x['total_contribution'])<=-D(level)/100*D(x['buy_cost'])]
        r[f'loss_ge_{level}_pct_count']=len(severe)
        r[f'loss_ge_{level}_pct_amount']=-sum((D(x['total_contribution']) for x in severe),Z)
    rows.append(r)
    for x in top[:5]:
        details.append(dict(period=period,cell=cell,layer=x['layer'],sid=x['sid'],signal_at=x['signal_at'],opened=x['opened'],closed=x['closed'],buy_cost=x['buy_cost'],contribution=x['total_contribution'],return_pct=100*D(x['total_contribution'])/D(x['buy_cost']),role=x['role'],pool=x['pool'],purpose=x['purpose'],entry_class=x['entry_class'],actual_reasons=sorted({s['reason'] for s in x['actual_sell_parts']})))
    gg=defaultdict(list)
    for x in ll:gg[(x['role'],x['pool'],x['purpose'],x['entry_class'])].append(x)
    for key,xx in sorted(gg.items()):
        cc=[x for x in xx if not x['remaining_qty']]
        buy=sum((D(x['buy_gross']) for x in xx),Z)
        neg=-sum((min(Z,D(x['total_contribution'])) for x in cc),Z)
        groups.append(dict(period=period,cell=cell,role=key[0],pool=key[1],purpose=key[2],entry_class=key[3],layers=len(xx),closed=len(cc),buy_gross=buy,buy_share_pct=100*buy/gross,negative_closed=neg,negative_to_own_all_buy_pct=100*neg/buy,positive_closed=sum((max(Z,D(x['total_contribution'])) for x in cc),Z),open_contribution=sum((D(x['total_contribution']) for x in xx if x['remaining_qty']),Z)))
    rr=defaultdict(list)
    for x in closed:
        rs={s['reason'] for s in x['actual_sell_parts']}
        funding=bool(rs&{'actionable_S_funding'})
        protection=bool(rs&{'I_structure_exit','CP1_old_line_exit'})
        kind='funding_only' if rs=={'actionable_S_funding'} else 'protection_only' if rs and rs<={'I_structure_exit','CP1_old_line_exit'} else 'mixed_funding_protection' if funding and protection else 'other'
        rr[kind].append(x)
    for kind,xx in sorted(rr.items()):
        reason_groups.append(dict(period=period,cell=cell,kind=kind,layers=len(xx),negative_count=sum(D(x['total_contribution'])<0 for x in xx),negative_amount=-sum((min(Z,D(x['total_contribution'])) for x in xx),Z),positive_amount=sum((max(Z,D(x['total_contribution'])) for x in xx),Z),buy_gross=sum((D(x['buy_gross']) for x in xx),Z)))
    assert sum((D(x['total_contribution']) for x in closed),Z)==r['positive_closed_amount']-loss
    assert len(closed)+len(opened)==len(ll)
assert all(digest(Path(p))==h for p,h in sources.items())
dump('SOURCE_SHA256.json',sources)
dump('SUMMARY.json',rows)
dump('GROUPS.json',groups)
dump('ACTUAL_EXIT_PATHS.json',reason_groups)
dump('WORST_FIVE_CLOSED.json',details)
with (HERE/'SUMMARY.csv').open('x') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(rows,ensure_ascii=False,indent=2,default=str))
