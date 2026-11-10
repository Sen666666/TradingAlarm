"""Frozen head-anchored greedy industry ordering; native admission remains intact."""
import math,collections,gzip,json
import pandas as pd

def ready(r):
    return bool(r.get('feature_ready',False)) and all(r.get(k) is not None and math.isfinite(float(r[k])) for k in ['h1','age','runup','scale','pvr']) and r['scale']>0

def industry_order(rows):
    remaining=sorted(rows,key=lambda r:(-r['h1'],r['symbol']));result=[];steps=[]
    while remaining:
        h=remaining[0];peers=[h]
        if ready(h):
            peers=[r for r in remaining if ready(r) and abs(r['h1']-h['h1'])<=1 and abs(r['age']-h['age'])<=5 and abs(r['runup']-h['runup'])<=max(r['scale'],h['scale'])]
            c=min(peers,key=lambda r:(-r['pvr'],-r['h1'],r['symbol']))
        else:c=h
        if c['symbol']!=h['symbol']:
            steps.append(dict(head=h['symbol'],chosen=c['symbol'],h1_head=h['h1'],h1_chosen=c['h1'],age_head=h['age'],age_chosen=c['age'],runup_head=h['runup'],runup_chosen=c['runup'],scale_head=h['scale'],scale_chosen=c['scale'],pvr_head=h['pvr'],pvr_chosen=c['pvr'],position=len(result)+1,neighbors=[r['symbol'] for r in peers]))
        result.append(c['symbol']);remaining=[r for r in remaining if r['symbol']!=c['symbol']]
    return result,steps

class Adapter:
    def __init__(self,P,risk,path):
        self.P=P;self.A=P.E.admission;self.L=P.E.ledger;self.old_priority=self.A._priority;self.old_decide=self.A.decide;self.old_commit=self.L.commit_cutoff
        self.lookup={(str(r.date.date()),r.symbol):r._asdict() for r in risk.itertuples(index=False)}
        self.stream=gzip.open(path,'wt',compresslevel=1);self.current=None;self.counts=collections.Counter()
    def install(self):
        self.A._priority=self.priority;self.A.decide=self.decide;self.L.commit_cutoff=self.commit
    def uninstall(self):
        self.A._priority=self.old_priority;self.A.decide=self.old_decide;self.L.commit_cutoff=self.old_commit;self.stream.close()
    def priority(self,ids,securities,sectors,resolved,clock,variant,fallbacks,batch):
        original=self.old_priority(ids,securities,sectors,resolved,clock,variant,fallbacks,batch)
        if variant!='S0' or batch!='waiting':
            self.counts['unchanged_'+batch]+=1;return original
        self.counts['waiting_calls']+=1;groups={};day=str(clock.decision_at.date())
        for sid in original:groups.setdefault(resolved[sid].sector_id,[]).append(sid)
        queues={};promotions=[]
        for sector,stockids in groups.items():
            rr=[]
            for sid in stockids:
                h1=securities[sid].rank.read(clock);r=self.lookup.get((day,sid))
                if r is None:
                    self.counts['feature_row_missing']+=1;r=dict(symbol=sid,h1=h1,feature_ready=False)
                else:
                    assert round(float(r['h1']),12)==h1,(day,sid,'H1 identity',r['h1'],h1)
                    r=dict(r,h1=h1)
                    if not ready(r):self.counts['feature_values_missing']+=1
                rr.append(r)
            queues[sector],ss=industry_order(rr)
            for s in ss:s['sector']=sector;promotions.append(s)
        result=[q[n] for n in range(max(map(len,queues.values()),default=0)) for q in queues.values() if n<len(q)]
        assert len(result)==len(original) and set(result)==set(original)
        if original!=result:
            self.counts['changed_priority_calls']+=1
            assert self.current is not None
            self.current['priority_changes'].append(dict(original=original,local=result,promotions=promotions))
        return result
    def decide(self,**kw):
        before=len(self.current['priority_changes']) if self.current else 0
        local=self.old_decide(**kw)
        if self.current is not None and len(self.current['priority_changes'])>before:
            self.A._priority=self.old_priority
            try:shadow=self.old_decide(**kw)
            finally:self.A._priority=self.priority
            assert local.exit_requests==shadow.exit_requests
            assert local.continue_buys==shadow.continue_buys
            self.current['recommendations'].append(dict(original=list(shadow.selected),local=list(local.selected),original_rejected=list(shadow.rejected),local_rejected=list(local.rejected),changed=local.selected!=shadow.selected,priority_change_indices=list(range(before,len(self.current['priority_changes'])))))
        return local
    def commit(self,a,**kw):
        assert self.current is None
        scenario='delay1' if a.delay_events else 'cost2' if a.cost_multiplier==2 else 'base'
        begin=len(a.audit_log);clock=kw['clock']
        ctx=dict(account='I__S0_'+scenario,at=str(clock.decision_at),available_before=str(a.available),nav_before=str(a.current_nav),risk_before=dict(a.risk_state),positions_before={s:p.shares for s,p in a.positions.items()},pending_buys_before=list(a.buys),priority_changes=[],recommendations=[])
        self.current=ctx
        try:
            ack=self.old_commit(a,**kw)
            ctx.update(accepted=list(ack.accepted),rejected=list(ack.rejected),entry_contracts=[r for r in a.audit_log[begin:] if r['kind']=='entry_contract'],available_after=str(a.available),counts=dict(self.counts))
            self.stream.write(json.dumps(self.P.C.native.encoded(ctx),ensure_ascii=False,allow_nan=False)+'\n')
            return ack
        finally:self.current=None
