"""Deterministic boundaries using the actual local adapter and native money helpers."""
from campaign_engine import *
import copy

def test():
    s=load_engine('2024_924');sid='000001.SZ';cal=pd.bdate_range('2024-10-08',periods=10);s.cal=cal
    raw=pd.DataFrame(dict(raw_open=10.,raw_close=10.,adjustment_factor=1.,source_kind='TEST',source_path='TEST',segment_id='TEST',observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False),index=cal)
    facts=pd.DataFrame(dict(i_target=1,i_floor=8.),index=cal);facts.loc[cal[7]:,'i_target']=0
    cp=pd.DataFrame(dict(receipt=False,candidate=8.,ready=True),index=cal);cp.loc[[cal[0],cal[1],cal[2],cal[3],cal[5]],'receipt']=True
    ev=pd.DataFrame(dict(event=0),index=cal);ev.loc[[cal[1],cal[3],cal[6],cal[7]],'event']=-1
    s.raw[sid]=s.DayFrame(raw);s.facts[sid]=s.DayFrame(facts);s.cp[sid]=s.DayFrame(cp);s.capacity[sid]={d:10000 for d in cal};s.closecache={};s.sector={'TEST':{d:1 for d in cal}}
    s.local_actions=lambda _:dict(events=[],coverage_evidence=[],unresolved=[],raw_response_empty=False,_source_integrity_ok=True,_source_issues=[],_source_coverage_issues=[])
    event=dict(sid=sid,economic_event_id=sid+'|SYNTHETIC',evidence_version='test',record_date=cal[1],ex_date=cal[2],pay_date=cal[6],d_cash=D('.1'),d_source=D('.1'),entitlement_verified=True)
    s.BY_RECORD={cal[1]:[event]};s.BY_EX={cal[2]:[event]};s.BY_PAY={cal[6]:[event]};s.EVENT_AT={}
    r=dict(event_id='TEST0',window='2024_924',sid=sid,name='TEST',industry='TEST',sector='TEST',day=cal[0],PVR_score=1.,I_qualified=True,PVR_known=True,i_floor=8.,event_type='A_SECTOR_BIRTH')
    base=dict(round_id='SYNTHETIC',window='2024_924',sid=sid,signal_day=cal[0],evidence_usable_closed=False,status='SYNTHETIC')
    roots=pd.Series(cal[0],index=cal);roots.loc[cal[7]:]=pd.NaT
    mp=dict(f=facts,cp=cp,ev=ev,b=raw,ok=pd.Series(True,index=cal),known=pd.Series(True,index=cal),same=pd.Series(True,index=cal),roots=roots)
    inv={d:dict(r,day=d,event_id='TEST'+str(i),event_type='B_STOCK_BIRTH_DURING_SECTOR') for i,d in [(2,cal[2]),(4,cal[4]),(7,cal[7])]}
    z=run_campaign(s,base,r,'C',mp,inv);a=z['actions'];attempt=z['attempts'];checks={}
    assert [x['side'] for x in a]==['buy_core','sell_all']*3
    assert [pd.Timestamp(x['day']) for x in a]==list(cal[[1,2,3,4,5,8]])
    checks['entry_day_down_tplusone_exit_and_close_invite_next_open']=True
    assert a[1]['reason']==a[3]['reason']=='TRIAL_DOWN_FIRST';assert a[5]['reason']=='I_STRUCTURE_EXIT'
    checks['down_cp_tie_down_wins_and_i_off_priority']=True
    assert attempt[1]['down_day']==cal[3] and attempt[1]['confirmed_day'] is None
    assert attempt[2]['confirmed_day']==cal[5] and attempt[2]['down_day'] is None
    checks['signal_cp_not_reused_new_trial_and_confirmed_ignores_later_down']=True
    assert a[2]['q']<a[0]['q'];assert z['campaign']['cash']>=0
    assert len(z['claims'])==1 and z['claims'][0]['owner_round_id']==attempt[0]['round_id'] and z['claims'][0]['settled']
    assert any(x['event']=='PAY_CLOSE' and x['day']==cal[6] for x in z['cash_ledger'])
    assert abs(z['campaign']['cash']+z['campaign']['receivable']-z['campaign']['initial_cost']-z['campaign']['net'])<1e-7
    checks['cash_only_integer_lots_and_old_attempt_payout_single_credit']=True
    assert z['campaign']['attempts']==3 and z['campaign']['permits']==1
    checks['multiple_losses_one_campaign_and_no_reentry_after_i_off']=True
    # Missing sale OPEN must freeze, never invent FLAT/reentry.
    raw.loc[cal[2],'raw_open']=np.nan;s.raw[sid]=s.DayFrame(raw);s.closecache={}
    zz=run_campaign(s,base,r,'C',mp,inv)
    assert len(zz['actions'])==1 and zz['campaign']['attempts']==1 and not zz['campaign']['execution_closed']
    checks['missing_sale_open_is_unknown_not_flat']=True
    # Source discontinuity cannot become a fresh usable root or allow recovery.
    raw.loc[cal[2],'raw_open']=10.;raw.loc[cal[2]:,'source_path']='OTHER';s.raw[sid]=s.DayFrame(raw);s.closecache={}
    mm=dict(mp,same=mp['same'].copy());mm['same'].loc[cal[2]]=False
    zz=run_campaign(s,base,r,'C',mm,inv)
    assert len(zz['actions'])==1 and zz['campaign']['root_unknown'] and zz['campaign']['attempts']==1
    checks['source_break_no_reconnected_campaign']=True
    write=O/'SYNTHETIC_ABC_FINAL_QA.json';assert not write.exists();write.write_text(json.dumps(dict(checks=checks,pass_all=all(checks.values()),engine_sha256=sha(O/'campaign_engine.py'),test_sha256=sha(Path(__file__))),indent=2)+'\n')
    print(json.dumps(checks,indent=2))
if __name__=='__main__':test()
