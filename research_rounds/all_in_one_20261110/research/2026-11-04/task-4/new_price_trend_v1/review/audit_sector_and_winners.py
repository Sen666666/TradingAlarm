"""Read-only all126 H1 attribution and original-winner actual-new-path join audit."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import csv,gzip,hashlib,json,sys,time
O=Path(__file__).resolve().parents[1];A=O/'analysis';R=Path(__file__).resolve().parent;Z=D(0)
def j(p):return json.loads(Path(p).read_text())
def gz(p,lines=False):
    with gzip.open(p,'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def n(v):return D(str(v))
def eq(a,b,label):assert abs(n(a)-n(b))<D('.000001'),(label,a,b)
def main():
    start=time.monotonic();sources=j(A/'SEMICONDUCTOR_PERIOD_SOURCE_SHA256.json');assert all(sha(p)==h for p,h in sources.items());summary=j(A/'SEMICONDUCTOR_H1_ACCOUNT_COMPARISON.json');old18={r['sid']for r in j(O.parent/'POST_PURCHASE_ALL18_STOCKS.json')};labels={r['sid']:r for r in j(O.parent/'SEMICONDUCTOR_ALL126_COMPARISON.json')if r['policy']=='PVR_NO60'};assert len(old18)==18 and len(labels)==126 and old18<=set(labels)
    sys.path.insert(0,str(O));import native_mark_reader as MARK
    carry_new={};carry_examples=[]
    for mode in ['OFF','BB20']:
        table=j(A/(mode+'_ALL126_H1_PERIOD_PARTICIPATION.json'));by={r['sid']:r for r in table};assert len(table)==len(by)==126 and set(by)==set(labels)
        assert sum(r['H1_price_label_unknown']for r in table)==12
        for sid,r in by.items():assert r['H1_price_label']==labels[sid]['H1_price_return_pct']and r['H1_price_label_unknown']==(labels[sid]['H1_price_return_pct']is None)and r['in_original_H1_18']==(sid in old18)
        with(A/(mode+'_ALL126_H1_PERIOD_PARTICIPATION.csv')).open()as h:c=list(csv.DictReader(h))
        assert len(c)==126 and {r['sid']for r in c}==set(by)
        for r in c:
            for k,v in by[r['sid']].items():assert r[k]==(''if v is None else str(v)),(mode,r['sid'],k)
        b=gz(O/'funding/runs'/('strong_'+mode)/'pair/B.json.gz');ds=gz(O/'funding/runs'/('strong_'+mode)/'pair/daily.jsonl.gz',True);daily={r['at'][:10]:r for r in ds};days=[d for d in sorted(daily)if '2025-12-31'<d<='2026-06-30'];assert len(days)==116
        cash={d:defaultdict(lambda:Z)for d in ['2025-12-31','2026-06-30']};buy=defaultdict(lambda:Z);fills=defaultdict(int)
        for t in b['trades']:
            sid=t['security_id']
            if sid not in by:continue
            gross=n(t['gross_cny']);fee=n(t['fees_cny']);date=t['at'][:10];flow=gross-fee if t['side']=='sell'else-gross-fee
            for end in cash:
                if date<=end:cash[end][sid]+=flow
            if '2025-12-31'<date<='2026-06-30'and t['side']=='buy':buy[sid]+=gross+fee;fills[sid]+=1
        for e in b['audit']:
            if e['kind']!='dividend_accrual':continue
            d=e['receivable'];sid=d['security_id']
            if sid not in by:continue
            for end in cash:
                if d['ex_at'][:10]<=end:cash[end][sid]+=n(d['net_local'])
        for sid,r in by.items():
            inventory={end:D(daily[end]['positions'].get(sid,0))*MARK.price(sid,end)if daily[end]['positions'].get(sid,0)else Z for end in cash};wealth={end:cash[end][sid]+inventory[end]for end in cash};held=[d for d in days if daily[d]['positions'].get(sid,0)]
            eq(r['actual_pre_H1_inventory'],inventory['2025-12-31'],(mode,sid,'pre inventory'));eq(r['actual_H1_end_inventory'],inventory['2026-06-30'],(mode,sid,'end inventory'));eq(r['actual_H1_wealth_change'],wealth['2026-06-30']-wealth['2025-12-31'],(mode,sid,'H1 wealth'));eq(r['actual_H1_buy_cash'],buy[sid],(mode,sid,'buy cash'));assert r['actual_H1_buy_fills']==fills[sid]and r['actual_H1_held_CLOSEs']==len(held)
            weight=sum((D(daily[d]['positions'][sid])*MARK.price(sid,d)/n(daily[d]['nav'])*100 for d in held),Z)/116;eq(r['actual_H1_mean_NAV_weight_pct'],weight,(mode,sid,'weight'));eq(r['actual_H1_contribution_pct_own_start_NAV'],n(r['actual_H1_wealth_change'])/n(daily['2025-12-31']['nav'])*100,(mode,sid,'contribution'))
            if inventory['2025-12-31']>0:carry_examples.append(dict(mode=mode,sid=sid,pre_inventory=str(inventory['2025-12-31']),H1_buy_fills=fills[sid],H1_wealth_change=r['actual_H1_wealth_change']))
        for group,predicate in [('all126',lambda r:True),('original18',lambda r:r['in_original_H1_18']),('other108',lambda r:not r['in_original_H1_18'])]:
            rs=[r for r in table if predicate(r)];s=summary[mode][group];assert (s['stocks'],s['actually_held_stocks'],s['new_buy_stocks'],s['actual_buy_fills'])==(len(rs),sum(r['actual_H1_held_CLOSEs']>0 for r in rs),sum(r['actual_H1_buy_fills']>0 for r in rs),sum(r['actual_H1_buy_fills']for r in rs))
            for k,col in [('buy_cash','actual_H1_buy_cash'),('wealth_change','actual_H1_wealth_change'),('mean_NAV_weight_pct','actual_H1_mean_NAV_weight_pct')]:eq(s[k],sum((n(r[col])for r in rs),Z),(mode,group,k))
        expected=next(r for r in j(A/('strong_'+mode+'_INDUSTRIES.json'))if r['period']=='2026H1'and r['industry']=='半导体');eq(expected['wealth_change'],summary[mode]['all126']['wealth_change'],(mode,'sector wealth'));eq(expected['mean_NAV_weight_pct'],summary[mode]['all126']['mean_NAV_weight_pct'],(mode,'sector weight'))
        # Actual carried-layer interval contribution vs actual new H1-layer net,
        # without proportional old PnL or hypothetical deletes.
        final={r['layer']:r for r in j(A/('strong_'+mode+'_LAYERS.json'))};pre={r['id']:r for r in daily['2025-12-31']['layers']};carried=new=Z
        for lid,l in final.items():
            if l['sid']not in by:continue
            if l['opened'][:10]>'2025-12-31':new+=n(l['net'])
            elif lid in pre:
                p=pre[lid];before=n(p['cash'])+n(p['dividend'])+D(p['qty'])*MARK.price(l['sid'],'2025-12-31');carried+=n(l['net'])-before
        eq(carried+new,summary[mode]['all126']['wealth_change'],(mode,'carry vs new layer interval bridge'));carry_new[mode]=dict(carried_2025_layers_H1_wealth=str(carried),new_H1_layers_net=str(new))
    winners=j(A/'ORIGINAL_TOP10_WINNER_COVERAGE.json');comparisons=j(A/'ACCOUNT_COMPARISONS.json');winner_proof={}
    for w in ['long','strong']:
        old=j(A/(w+'_OFF_STOCKS.json'));new={r['sid']:r for r in j(A/(w+'_BB20_STOCKS.json'))};expected=sorted(old,key=lambda r:-n(r['net']))[:10];got=[r for r in winners if r['window']==w];assert len(got)==10
        for a,b in zip(got,expected):assert a['original_winner']==b and a['new']==new.get(b['sid'])
        oldmap={r['sid']:r for r in old};delta=j(A/(w+'_STOCK_DELTAS.json'));assert {r['sid']for r in delta}==set(oldmap)|set(new)
        for r in delta:
            assert r['old']==oldmap.get(r['sid'])and r['new']==new.get(r['sid']);eq(r['net_delta'],(n(r['new']['net'])if r['new']else Z)-(n(r['old']['net'])if r['old']else Z),(w,r['sid'],'actual path stock delta'))
        eq(sum((n(r['net_delta'])for r in delta),Z),n(comparisons[w]['new']['all']['end_NAV'])-n(comparisons[w]['old']['all']['end_NAV']),(w,'stock delta NAV bridge'))
        assert comparisons[w]['new_stock_count']==len(set(new)-set(oldmap))and comparisons[w]['lost_stock_count']==len(set(oldmap)-set(new))
        winner_proof[w]=dict(original_top10=10,not_traded_in_new=sum(r['new']is None for r in got),actual_new_minus_old_top10_net=str(sum(((n(r['new']['net'])if r['new']else Z)-n(r['original_winner']['net'])for r in got),Z)),scope='Ex post evaluation identities and actual complete new-account stock contributions; no direct gate-block or single-trade causal attribution claimed.')
    out=dict(passed=True,status='PASS_ALL126_PERIOD_PARTICIPATION_AND_ACTUAL_WINNER_JOIN',stocks_per_mode=126,original18=18,other108=108,unknown_price_labels_per_mode=12,H1_closes=116,all_rows_and_CSV_exact=True,all_sector_cash_dividend_inventory_period_wealth_exact=True,actual_carry_vs_new_layer_bridge=carry_new,carried_stocks=carry_examples,original_winner_actual_new_path_join=winner_proof,reviewer_accounts=0,reviewer_projections=0,seconds=time.monotonic()-start,scope='H1 wealth includes pre-H1 inventory; mean weights use own account NAV each day and each own H1 start NAV is retained. Price endpoint labels remain evaluation only, including unknown. Observed fewer semis and positive small wealth do not establish sufficient major-trend participation.')
    (R/'SECTOR_AND_WINNER_RESULT_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
