from pathlib import Path
p=Path(__file__).with_name('unified_probe.py');s=p.read_text()
s=s.replace("and any(x.stock==stock and x.qty>0 for x in self.lots))", "and self.confirmed_stock_lot(stock,sector))")
pos=s.index('    def promote_stock(')
s=s[:pos]+'''    def confirmed_stock_lot(self,stock,sector):
        state=self.sectors[sector]
        return any(x.stock==stock and x.sector==sector and x.qty>0 and x.pool=='confirmed' and x.episode==state.episode and x.attempt==state.attempt for x in self.lots)
'''+s[pos:]
s=s.replace("        if held and role=='mobile' and b.expand and s.level>0:routes.append('confirmed')", "        if held and role=='mobile' and b.expand and s.level>0 and b.confirmed_stock_lot(sid,sector):routes.append('confirmed')")
s=s.replace("                    # Only reduces the original frozen target. OPEN enforces risk.\n                    i['cap']=min(i['cap'],i['quote'].quantity.buy_floor(int(i['budget']/i['quote'].raw_price)))", "                    # Freeze a joint cash/risk cap at decision CLOSE; OPEN may\n                    # reduce it, but a favorable gap cannot create new shares.\n                    quote=i['quote'];ref=quote.raw_price*(1+LR.SLIP);rawfloor=i['floor']/self.facts.factor(i['sid'],at)\n                    maxq=min(i['cap'],int(i['budget']/ref))\n                    i['cap']=LR.maximum_quantity(quote.quantity,maxq,lambda q:LR.protection_risk(q,ref,rawfloor,quote.fees,quote.par_value)<=i['_flat_risk_budget'])")
s=s.replace("        for i in sorted(getattr(a,'promotion_candidates',[]),key=lambda x:x['sid']):", "        prepared=[]\n        for i in sorted(getattr(a,'promotion_candidates',[]),key=lambda x:x['sid']):")
s=s.replace("            self.promote_candidate(a,i,D(str(raw.loc[day].open)),at)\n    def net_verdict", "            proof=self.promote_candidate(a,i,D(str(raw.loc[day].open)),at,prepare_only=True)\n            if proof is not None:prepared.append(proof)\n        # Every proof was computed before any pool mutation, on the same\n        # post-sell/pre-buy snapshot. Commits cannot affect other eligibility.\n        for proof in prepared:self.commit_promotion(a,proof)\n    def net_verdict")
s=s.replace("    def promote_candidate(self,a,i,op,at):", "    def promote_candidate(self,a,i,op,at,prepare_only=False):")
a=s.index("        if op<=floor:moved,reason=[]");b=s.index('    def route(',a)
s=s[:a]+'''        reason='open_at_or_below_protection' if op<=floor else 'nonprofitable_remaining_holding' if not verdict['allowed'] else 'eligible'
        proof=dict(i=i,op=op,at=at,token=token,bar=bar,verdict=verdict,floor=floor,reason=reason)
        if prepare_only:return proof
        return self.commit_promotion(a,proof)
    def commit_promotion(self,a,proof):
        i,op,at,token,bar,verdict,floor,reason=(proof[k] for k in ('i','op','at','token','bar','verdict','floor','reason'))
        b=a.budget;sid=i['sid'];sector=self.sector_by_sid[sid];s=b.sectors[sector]
        if reason=='eligible':moved,reason=b.promote_stock(sid,sector,token,bar,verdict['net_profit'])
        else:moved=[]
        if moved:
            a.pools_from_model()
            for layer in moved:assert a.jmeta[int(layer)]['pool']=='confirmed'
            a.assert_budget_view(at)
        event=dict(account=a.label,sid=sid,at=at,CP1_id=i['CP1_id'],signal_at=i['clock'].decision_at,attempt=s.attempt,moved=moved,reason=reason,known_open=op,effective_floor=floor,independent_of_buy=True,CP_consumed=token.event_id in b.consumed,**verdict)
        self.promotion_events.append(event)
        return event
'''+s[b:]
p.write_text(s)
t=Path(__file__).with_name('test_unified.py');s=t.read_text().replace("self.journal=[];self.buys={};", "self.journal=[];self.positions={x.stock:object() for x in b.lots};self.buys={};")
t.write_text(s)
