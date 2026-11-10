"""Fixed sample/full driver. Full requires explicit independent audit artifact."""
from campaign_engine import *
import sys,time

def writejson(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')

def main(mode):
    assert mode in ['sample','sample_d','full']
    arms=['D'] if mode=='sample_d' else ['A','B','C','D'] if mode=='full' else ['A','B','C']
    dest=O/mode;assert not dest.exists(),('one-shot destination exists',dest)
    if mode=='full':
        approval=json.loads((O/'INDEPENDENT_PRE_ECONOMIC_APPROVAL.json').read_text());assert approval['full_run_approved'] is True
        assert set(approval['code_hashes'])=={'campaign_engine.py','run_campaigns.py','causal_invites.py','PRE_ECONOMIC_DESIGN.md','native_role_adapter.py','native_fast_inputs.py','D_SCOPE_PENDING_REVIEW.md','causal_ab_birth_knowledge.py','report_campaigns.py'}
        for name,h in approval['code_hashes'].items():assert sha(O/name)==h,('audited code changed',name)
    seals=[R/'cross_window_entry_mechanism_v1/BASELINE_SOURCE_HASHES.json',R/'first_evidence_race_preflight_v1/SOURCE_HASHES.json',O/'CAUSAL_INVITES_SOURCE_HASHES.json',O/'CAUSAL_INVITES_ARTIFACT_HASHES.json',O/'AB_BIRTH_KNOWLEDGE_SOURCE_HASHES.json',O/'AB_BIRTH_KNOWLEDGE_ARTIFACT_HASHES.json']
    if 'D' in arms:seals += [O/'NATIVE_FAST_INPUT_SOURCE_HASHES.json',O/'NATIVE_FAST_INPUT_OUTPUT_HASHES.json']
    sealed={}
    for seal in seals:
        data=json.loads(seal.read_text());data=data.get('artifacts',data)
        for path,h in data.items():
            pp=Path(path) if Path(path).is_absolute() else O/path
            assert sha(pp)==h,(str(pp),'input seal mismatch');sealed[str(pp)]=h
    baseline=pd.read_csv(R/'cross_window_entry_mechanism_v1/BASELINE_EXISTING_CONTEXT.csv',dtype={'window':str},low_memory=False)
    pre=pd.read_csv(R/'first_evidence_race_preflight_v1/RACE_WITH_OLD_LABELS.csv',dtype={'window':str},low_memory=False)
    assert len(baseline)==4086 and baseline.round_id.is_unique
    events=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',dtype={'window':str},parse_dates=['day'],low_memory=False).set_index('event_id')
    if mode in ['sample','sample_d']:
        chosen=set(pre.loc[pre.evidence_usable_closed.eq(True)&pre.core_return.ge(.5)&pre.race.eq('DOWN_FIRST'),'round_id']);assert len(chosen)==19
        for _,g in pre.groupby(['window','race'],dropna=False):chosen.update(g.sort_values('round_id').head(1).round_id)
        chosen.update(pre.loc[pre.original_status.astype(str).str.contains('NOFILL')].sort_values('round_id').head(2).round_id)
        work=baseline[baseline.round_id.isin(chosen)].copy()
    else:work=baseline
    invitation_path=O/'ALL_MARKET_AB_INVITES.parquet'
    inv=pd.read_parquet(invitation_path);inv['day']=pd.to_datetime(inv.day)
    knowledge=pd.read_parquet(O/'AB_BIRTH_KNOWLEDGE.parquet').groupby('sid',sort=False)
    nativegroups=None;canonical={}
    if 'D' in arms:
        nativegroups=pd.read_parquet(O/'NATIVE_FAST_INPUTS.parquet').groupby('sid',sort=False)
        cp=pd.read_parquet(R/'fast_entry_equity_2022_v1/CANONICAL_CP_2022_2026.parquet')
        for rr in cp.to_dict('records'):
            unknown=rr.get('trace_unknown',[]);known=not len(unknown) if isinstance(unknown,(list,tuple,np.ndarray)) else unknown in (None,'','[]')
            canonical[(rr.get('sid',rr.get('canonical_series')),pd.Timestamp(rr.get('day',rr.get('confirmed_day'))))]=dict(cp_id=rr.get('cp_id',rr.get('receipt_id')),known=known)
    dest.mkdir()
    writejson(dest/'RUN_ONCE.json',dict(stage=mode,started=str(pd.Timestamp.now(tz='UTC')),rows=len(work),fixed_ids=work.round_id.tolist(),hashes={str(p):sha(p) for p in [Path(__file__),O/'campaign_engine.py',O/'causal_invites.py',O/'PRE_ECONOMIC_DESIGN.md',invitation_path]},account=False,parameter_scan=False))
    writejson(dest/'VERIFIED_INPUT_SEALS.json',sealed)
    campaigns=[];attempts=[];actions=[];claims=[];ledger=[];decisions=[];recon=[];native_consumptions=[];native_roles=[];sources={};start=time.time()
    for window,g in work.groupby('window'):
        s=load_engine(window)
        for sid,gg in g.groupby('sid'):
            mp=market_path(s,sid);ii=inv[inv.sid.eq(sid)];assert not ii.day.duplicated().any();imap={r['day']:r for r in ii.to_dict('records')}
            kk=knowledge.get_group(sid);kmap=dict(zip(pd.to_datetime(kk.day),kk.ab_birth_known))
            nmap={pd.Timestamp(r['day']):r for r in nativegroups.get_group(sid).to_dict('records')} if nativegroups is not None else {}
            for r in gg.to_dict('records'):
                event=events.loc[r['event_id']].to_dict();event['event_id']=r['event_id']
                for arm in arms:
                    out=run_campaign(s,r,event,arm,mp,imap,nmap,canonical,kmap);native_consumptions+=out['native_consumptions'];native_roles+=out['native_role_attempts'];campaigns.append(out['campaign']);attempts+=out['attempts'];actions+=out['actions'];claims+=out['claims'];ledger+=out['cash_ledger'];decisions+=out['invitation_decisions']
                    if arm=='A':
                        a=out['attempts'][0];q=dict(round_id=r['round_id'],old_usable=r['evidence_usable_closed'],new_usable=a['evidence_usable_closed'],status_old=r['status'],status_new=a['status'])
                        for field in ['entry_day','entry_q','entry_price','exit_day','exit_price']:
                            x=a.get(field);y=r.get(field)
                            if pd.isna(x) and pd.isna(y):ok=True
                            elif field.endswith('day'):ok=pd.Timestamp(x)==pd.Timestamp(y)
                            else:ok=x is not None and np.isclose(float(x),float(y),atol=1e-7,rtol=1e-12)
                            q[field+'_match']=bool(ok)
                        q['old_core_net']=r.get('core_net');q['new_core_net']=a.get('net_pnl');q['net_delta']=a.get('net_pnl',np.nan)-r.get('core_net',np.nan)
                        components={'core_return':a.get('net_return_on_buy_cash'),'core_buy_fee':a.get('entry_fee'),'core_sell_fee':a.get('all_fees',np.nan)-a.get('entry_fee',np.nan),'core_dividend_net80':a.get('dividend_net80_total'),'core_buy_cash':a.get('total_buy_cash')}
                        for field,value in components.items():
                            q[field+'_old']=r.get(field);q[field+'_new']=value
                            q[field+'_match']=pd.isna(value) and pd.isna(r.get(field)) or (value is not None and np.isclose(float(value),float(r.get(field)),atol=1e-7,rtol=1e-12))
                        if r['evidence_usable_closed']:
                            assert all(q[field+'_match'] for field in components),(r['round_id'],'component reconciliation',q)
                            assert all(q[f+'_match'] for f in ['entry_day','entry_q','entry_price','exit_day','exit_price']),(r['round_id'],q)
                            assert a['evidence_usable_closed'] and abs(q['net_delta'])<=1e-7,(r['round_id'],q)
                        recon.append(q)
            sources.update(s.hashes)
            print(mode,window,sid,'permits',len(recon),'sec',round(time.time()-start,1),flush=True)
    for name,rows in [('CAMPAIGNS',campaigns),('ATTEMPTS',attempts),('ACTIONS',actions),('CASH_LEDGER',ledger),('INVITATION_DECISIONS',decisions),('INITIAL_RECONCILIATION',recon),('NATIVE_CONSUMPTIONS',native_consumptions),('NATIVE_ROLE_ATTEMPTS',native_roles)]:pd.DataFrame(rows).to_csv(dest/(name+'.csv'),index=False)
    writejson(dest/'CLAIMS.json',claims);writejson(dest/'SOURCE_HASHES.json',sources)
    for p,h in sources.items():assert sha(p)==h,(p,'post run drift')
    z=pd.DataFrame(campaigns);summary=[]
    for arm,g in z[z.evidence_usable_closed].groupby('arm'):assert not g.campaign_key.duplicated().any(),('campaign duplicated',arm)
    common=set(z[z.evidence_usable_closed].groupby('campaign_key').filter(lambda g:len(g)==len(arms)).campaign_key)
    z['all_arm_common_known']=z.evidence_usable_closed & z.campaign_key.isin(common)
    for arm,g in z[z.all_arm_common_known].groupby('arm'):assert not g.campaign_key.duplicated().any(),('common duplicate',arm)
    z.to_csv(dest/'CAMPAIGNS.csv',index=False)
    for (w,arm),g in z.groupby(['window','arm']):
        c=g[g.evidence_usable_closed];win=c[c.net>0];loss=c[c.net<=0]
        summary.append(dict(window=w,arm=arm,scope='ARM_KNOWN',permits=len(g),closed_usable=len(c),wins=len(win),win_rate=len(win)/len(c) if len(c) else None,net_sum=c.net.sum(),mean_net=c.net.mean(),average_win=win.net.mean(),average_loss=loss.net.mean(),payoff=win.net.mean()/-loss.net.mean() if len(win) and len(loss) and loss.net.mean()!=0 else None,attempts=g.attempts.sum(),fees=g.total_fees.sum(),not_account=True))
    for (w,arm),g in z[z.all_arm_common_known].groupby(['window','arm']):
        win=g[g.net>0];loss=g[g.net<=0]
        summary.append(dict(window=w,arm=arm,scope='ALL_ARM_COMMON_KNOWN',permits=len(g),closed_usable=len(g),wins=len(win),win_rate=len(win)/len(g),net_sum=g.net.sum(),mean_net=g.net.mean(),average_win=win.net.mean(),average_loss=loss.net.mean(),payoff=win.net.mean()/-loss.net.mean() if len(win) and len(loss) and loss.net.mean()!=0 else None,attempts=g.attempts.sum(),fees=g.total_fees.sum(),not_account=True))
    pd.DataFrame(summary).to_csv(dest/'SUMMARY_BY_WINDOW.csv',index=False)
    writejson(dest/'QA.json',dict(completed=True,permits=len(work),arm_rows=len(z),original_usable_A_reconciled=('A' in arms),source_hashes_pass=True,seconds=time.time()-start))
    print(pd.DataFrame(summary).to_string(index=False),flush=True)

if __name__=='__main__':main(sys.argv[1])
