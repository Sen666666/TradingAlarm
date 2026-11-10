from pathlib import Path
p=Path(__file__).with_name('unified_probe.py');s=p.read_text()
s=s.replace("        return False\n    def confirmed_stock_ready", "        state=self.sectors[sector]\n        if state.active and state.level>0:state.status='confirmed' if state.level==1 else 'expanded'\n        return False\n    def confirmed_stock_ready",1)
a=s.index('# Keep original opening structure');b=s.index('class UnifiedRunner',a)
s=s[:a]+'''# Exact native opening with one promotion phase after sells/settlement/sync,
# before original PVR allocation. Promotion-only evidence is not a buy intent.
OPEN_SOURCE=textwrap.dedent(inspect.getsource(J.Runner.opening))
_OPEN_ANCHOR=" a.settle_due(at);a.sync(at);funded=[];done=set()"
assert OPEN_SOURCE.count(_OPEN_ANCHOR)==1
OPEN_SOURCE=OPEN_SOURCE.replace(_OPEN_ANCHOR," a.settle_due(at);a.sync(at);self.promote_open_candidates(a,at);funded=[];done=set()")
_env=dict(J.__dict__);exec(compile(OPEN_SOURCE,str(HERE/'derived_opening.py'),'exec'),_env)
OPENING=_env['opening']

'''+s[b:]
a=s.index('            present={');b=s.index('    def net_verdict(',a)
s=s[:a]+'''            a.promotion_candidates=[]
            clock=None
            for row in self.opportunities[old:]:
                if row['account']!=a.label or not row['held'] or row['barriers'] or 'mobile' not in row['roles'] or row['mobile_Q'] is not True:continue
                sid=row['sid'];cp=self.receipts[sid].get(J.gidday(at));q=self.market.quote(sid,at);floor=self.facts.floor(sid,at,'I')
                if cp is None or q is None or floor is None:continue
                if clock is None:clock=self.facts.packet(at,'I')[0]
                floor=max(floor,D(str(self.cp[sid].loc[J.pd.Timestamp(at.date()),'candidate'])))
                a.promotion_candidates.append(dict(sid=sid,clock=clock,quote=q,role='mobile',floor=floor,CP1_id=cp['receipt_id'],CP1_trace=cp,_sector=row['sector']))
            decision['unified_intents']=[{k:v for k,v in i.items() if k not in ('quote','clock','CP1_trace')} for i in a.pending]
            decision['promotion_candidates']=[{k:v for k,v in i.items() if k not in ('quote','clock','CP1_trace')} for i in a.promotion_candidates]
    def promote_open_candidates(self,a,at):
        for i in sorted(getattr(a,'promotion_candidates',[]),key=lambda x:x['sid']):
            if i['clock'].earliest_execution_at!=at:continue
            raw=self.market.raw[i['sid']];day=J.pd.Timestamp(at.date())
            if day not in raw.index or not J.np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:continue
            self.promote_candidate(a,i,D(str(raw.loc[day].open)),at)
'''+s[b:]
s=s.replace("        floor=i['floor']/self.facts.factor(sid,at)\n        verdict=", "        assert i['CP1_trace']['receipt_id']==i['CP1_id'] and i['CP1_trace']['confirmed_day']==J.gidday(i['clock'].decision_at)\n        eligible=[x for x in a.live(sid) if a.jmeta[x['id']]['pool']=='probe' and a.jmeta[x['id']]['attempt']==s.attempt and a.jmeta[x['id']]['episode']==s.episode]\n        if not eligible:return\n        # New evidence must be confirmed after the actual probe fill. A fresh\n        # daily CP can confirm at CLOSE on the same date as the earlier OPEN.\n        if any(i['clock'].decision_at<=x['opened'] for x in eligible):return\n        floor=i['floor']/self.facts.factor(sid,at)\n        verdict=",1)
p.write_text(s)
