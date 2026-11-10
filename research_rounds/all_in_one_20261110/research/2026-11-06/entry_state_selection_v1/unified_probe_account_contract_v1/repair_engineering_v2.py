from pathlib import Path
p=Path(__file__).with_name('unified_probe.py');s=p.read_text().replace('import sys, inspect, textwrap, copy, hashlib','import sys, inspect, textwrap, copy, hashlib, pickle')
s=s.replace("_REQUEST=A.P.NEW_MODEL.split('    def request(',1)[1].split('    def fill(',1)[0]\nREQUEST_SOURCE='def request('+textwrap.dedent(_REQUEST)\n# Dedent after reconstructing the complete method, not its first line alone.\n",'')
pos=s.index('class UnifiedRunner')
s=s[:pos]+'''def prune_restore_keys(r,snapshot):
    """Legacy restore updates keys but cannot remove caches born after snapshot.
    Validate before any mutation. Preserve only the native immutable handles.
    """
    assert snapshot['source_freeze']==r.source_freeze,'resume input/code freeze differs'
    keep={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date'}
    removed={'runner':sorted(set(vars(r))-keep-set(snapshot['runner'])),'accounts':{}}
    for key in removed['runner']:del r.__dict__[key]
    for label,a in r.accounts.items():
        assert label in snapshot['accounts']
        keys=sorted(set(vars(a))-{'market','facts'}-set(snapshot['accounts'][label]))
        removed['accounts'][label]=keys
        for key in keys:del a.__dict__[key]
    return removed

'''+s[pos:]
s=s.replace("            if day not in raw.index or not J.np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:continue\n            proof=self.promote_candidate", "            if day not in raw.index:\n                self.promotion_reject(a,i,at,'missing_open',historical_tradability='UNKNOWN');continue\n            if not J.np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:\n                self.promotion_reject(a,i,at,'invalid_open',historical_tradability='UNKNOWN');continue\n            proof=self.promote_candidate")
a=s.index('    def promote_candidate(');b=s.index('        floor=i[\'floor\']/self.facts.factor(sid,at)',a)
s=s[:a]+'''    def promotion_reject(self,a,i,at,reason,**detail):
        self.promotion_events.append(dict(account=a.label,sid=i['sid'],at=at,signal_at=i['clock'].decision_at,CP1_id=i.get('CP1_id'),reason=reason,moved=[],allowed=False,independent_of_buy=True,**detail))
    def promote_candidate(self,a,i,op,at,prepare_only=False):
        sid=i['sid'];b=a.budget;sector=self.sector_by_sid[sid];s=b.sectors.get(sector)
        def reject(reason,**detail):self.promotion_reject(a,i,at,reason,**detail)
        if i['role']!='mobile':return reject('not_original_mobile_confirmation')
        if not a.quantity(sid):return reject('post_sell_qty_zero')
        if sid in a.buys or sid in a.exits:return reject('real_buy_or_exit_pending')
        if not(s and s.active and s.level>0 and b.expand):return reject('industry_not_expansion_authorized')
        i['_sector']=sector;token=token_for(b,i);bar=J.ordinal(i['clock'].decision_at.date())
        if not b.valid(token,'stock_cp1',bar) or token.event_id in b.consumed:return reject('no_fresh_stock_CP1')
        if i['CP1_trace']['receipt_id']!=i['CP1_id'] or i['CP1_trace']['confirmed_day']!=J.gidday(i['clock'].decision_at):return reject('CP_identity_or_date_mismatch')
        eligible=[x for x in a.live(sid) if a.jmeta[x['id']]['pool']=='probe' and a.jmeta[x['id']]['attempt']==s.attempt and a.jmeta[x['id']]['episode']==s.episode]
        if not eligible:return reject('no_eligible_probe_layers')
        if any(i['clock'].decision_at<=x['opened'] for x in eligible):return reject('CP_not_after_probe_fill')
        try:factor=D(str(self.facts.factor(sid,at)))
        except (ValueError,TypeError,KeyError,ArithmeticError):return reject('invalid_factor',price_domain='UNKNOWN')
        if not factor.is_finite() or factor<=0:return reject('invalid_factor',price_domain='UNKNOWN')
        if not op.is_finite() or op<=0:return reject('invalid_open',historical_tradability='UNKNOWN')
'''+s[b:]
s=s.replace("        floor=i['floor']/self.facts.factor(sid,at)\n        verdict=", "        floor=i['floor']/factor\n        if not floor.is_finite() or floor<=0:return reject('invalid_effective_floor',price_domain='UNKNOWN')\n        verdict=",1)
pos=s.index('    def assert_native_wiring(self):')
s=s[:pos]+'''    def restore(self,path):
        snapshot=pickle.loads(Path(path).read_bytes())
        # No legacy checkpoint is re-certified: outer atomic provenance and
        # parent policy/source-freeze guards remain in force.
        assert snapshot['runner']['integration_policy']==self.integration_policy
        assert snapshot['runner']['rank_scores_manifest_sha256']==self.rank_scores_manifest_sha256
        prune_restore_keys(self,snapshot)
        return A.Runner.restore(self,path)
'''+s[pos:]
p.write_text(s)
# Add a selectable new output directory and explicit lifecycle/diagnostic records.
p=Path(__file__).with_name('run_first_day.py');s=p.read_text()
s=s.replace(" out=HERE/'first_day_check';assert not out.exists(),'No overwrite or automatic rerun'", " import argparse\n parser=argparse.ArgumentParser();parser.add_argument('--out',default='first_day_check');args=parser.parse_args()\n assert '/' not in args.out and args.out not in ('.','..')\n out=HERE/args.out;assert not out.exists(),'No overwrite or automatic rerun'")
s=s.replace(" out.mkdir();started=time.monotonic();r=None;last=None", " out.mkdir();started=time.monotonic();r=None;last=None;normal_open_completed=False\n R.save(out/'STARTED.json',dict(status='RUNNING',scope='bounded Jan4-5 engineering only',full_window_run=False))")
s=s.replace("     R.event(r,m,at,opens,closes,None);normal=R.digest(R.payload(r))", "     R.event(r,m,at,opens,closes,None);normal=R.digest(R.payload(r));normal_open_completed=True\n     R.save(out/'NORMAL_OPEN_COMPLETED.json',dict(at=at,payload_sha256=normal,buy_fills=len(r.accounts['PVR'].trades),admission_events=r.admission_events))")
s=s.replace("  R.save(out/'FAILURE.json',dict(error=str(exc),traceback=traceback.format_exc(),last_complete_event=last));raise", "  R.save(out/'FAILURE.json',dict(error=str(exc),traceback=traceback.format_exc(),last_complete_event=last,normal_open_completed=normal_open_completed,partial_event_not_resumable=True,automatic_rerun=False))\n  if r is not None:R.IO.write_pickle(out/'PARTIAL_STATE_DIAGNOSTIC_ONLY.pkl',dict(status='FAILED_EVENT_NOT_A_RESUMABLE_CHECKPOINT',payload=R.payload(r)))\n  raise")
p.write_text(s)
p=Path(__file__).with_name('CONTRACT.md');s=p.read_text()+'''\n## Engineering corrections and current limitation\n\nThe first engineering attempt failed only during restored replay of Jan 5 OPEN. Legacy PreparedRunner.restore uses dict.update and did not remove `_ix`/`_ixn` layer caches created after an empty-account checkpoint. Normal OPEN had completed, but its detail was not persisted, so no first-day success or trade count is claimed from that failed attempt. Original failed directory remains intact. Isolated restore now validates source/policy/provenance and removes only mutable keys absent from the checkpoint, then calls original restore. Account fill, inventory and T+1 methods remain unchanged.\n\nEach promotion-only candidate receives an outcome, including missing/invalid OPEN, invalid factor/price domain, post-sell zero quantity, pending real orders, invalid industry or CP, and no matching layers. Missing market data remains UNKNOWN, not a claim of exchange suspension.\n\nNew user clarification about sectors having many right-side stocks is NOT resolved by this funding contract. Existing industry E0/CP qualification must not be described as satisfying an explicit stock-breadth gate. No new breadth threshold is introduced here; full-window economic launch is paused pending that separate contract decision.\n''';p.write_text(s)
