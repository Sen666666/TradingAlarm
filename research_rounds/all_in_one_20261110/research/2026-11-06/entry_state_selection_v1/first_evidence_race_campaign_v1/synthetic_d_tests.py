"""Fourth-arm native-role boundary checks. No parameter choice or market performance test."""
from campaign_engine import *
from native_role_adapter import NativeRoles

def main():
 s=load_engine('2024_924');sid='000001.SZ';cal=pd.bdate_range('2024-12-26',periods=10);s.cal=cal
 raw=pd.DataFrame(dict(raw_open=10.,raw_close=10.,adjustment_factor=1.,source_kind='TEST',source_path='TEST',segment_id='TEST',observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False),index=cal)
 facts=pd.DataFrame(dict(i_target=1,i_floor=8.),index=cal);facts.loc[cal[7]:,'i_target']=0
 cp=pd.DataFrame(dict(receipt=False,candidate=8.,ready=True),index=cal);cp.loc[cal[:6],'receipt']=True
 ev=pd.DataFrame(dict(event=0),index=cal);ev.loc[[cal[1],cal[3],cal[6],cal[7]],'event']=-1
 s.raw[sid]=s.DayFrame(raw);s.facts[sid]=s.DayFrame(facts);s.cp[sid]=s.DayFrame(cp);s.capacity[sid]={d:10000 for d in cal};s.closecache={};s.sector={'TEST':{d:1 for d in cal}}
 s.local_actions=lambda _:dict(events=[],coverage_evidence=[],unresolved=[],raw_response_empty=False,_source_integrity_ok=True,_source_issues=[],_source_coverage_issues=[])
 event=dict(sid=sid,economic_event_id=sid+'|SYNTHETIC',evidence_version='test',record_date=cal[1],ex_date=cal[2],pay_date=END+pd.Timedelta(days=1),d_cash=D('.1'),d_source=D('.1'),entitlement_verified=True)
 s.BY_RECORD={cal[1]:[event]};s.BY_EX={cal[2]:[event]};s.BY_PAY={event['pay_date']:[event]};s.EVENT_AT={}
 r=dict(event_id='TEST0',window='2024_924',sid=sid,name='TEST',industry='TEST',sector='TEST',day=cal[0],PVR_score=1.,PVR_known=True,I_qualified=True,i_floor=8.,event_type='A_SECTOR_BIRTH')
 base=dict(round_id='SYNTHETIC_D',window='2024_924',sid=sid,signal_day=cal[0],evidence_usable_closed=False,status='SYNTHETIC')
 roots=pd.Series(cal[0],index=cal);roots.loc[cal[7]:]=pd.NaT
 mp=dict(f=facts,cp=cp,ev=ev,b=raw,ok=pd.Series(True,index=cal),known=pd.Series(True,index=cal),same=pd.Series(True,index=cal),roots=roots)
 nr={d:dict(r,day=d,i_epoch='ROOT_1',epoch_lineage_known=True,event_Q=True,continuing_Q=True,cp_fresh=bool(cp.loc[d,'receipt']),cp_trace_known=True,cp_id='CP'+str(k),cp_candidate=8.) for k,d in enumerate(cal)}
 canonical={(sid,d):dict(cp_id='CP'+str(k),known=True) for k,d in enumerate(cal) if cp.loc[d,'receipt']}
 z=run_campaign(s,base,r,'D',mp,{},nr,canonical);a=z['actions'];checks={}
 assert len(a)==6 and [pd.Timestamp(x['day']) for x in a]==list(cal[[1,2,3,4,5,8]])
 assert [x['kind'] for x in z['native_consumptions']]==['CORE_EPOCH','MOBILE_CP','MOBILE_CP']
 assert [x['identity'] for x in z['native_consumptions']]==['ROOT_1','CP2','CP4']
 checks['initial_ab_fill_consumes_core_no_free_epoch_recovery']=True
 assert z['attempts'][1]['entry_role']==z['attempts'][2]['entry_role']=='MOBILE_CP'
 assert z['attempts'][1]['down_day']==cal[3] and z['attempts'][1]['confirmed_day'] is None
 checks['fresh_id_only_and_new_trial_excludes_signal_cp']=True
 assert z['campaign']['receivable']>0 and not z['campaign']['cash_settled'] and z['campaign']['receivable_pending']
 assert all(x['event']!='PAY_CLOSE' for x in z['cash_ledger'])
 assert abs(z['campaign']['cash']+z['campaign']['receivable']-z['campaign']['initial_cost']-z['campaign']['net'])<1e-7
 checks['unpaid_terminal_claim_not_spent_and_accrual_cash_separate']=True
 assert cal[5].year!=cal[0].year and z['campaign']['attempts']==3
 checks['cross_year_same_root_not_reseeded']=True
 # Later CP candidate ratchets the active floor; next day violation exits by native role.
 cp.loc[cal[5],'candidate']=9.9;raw.loc[cal[6],'raw_close']=9.8;s.raw[sid]=s.DayFrame(raw);s.cp[sid]=s.DayFrame(cp);s.closecache={}
 zz=run_campaign(s,base,r,'D',mp,{},nr,canonical)
 assert zz['actions'][-1]['side']=='sell_initial' and zz['actions'][-1]['reason']=='CP_INITIAL_FLOOR' and pd.Timestamp(zz['actions'][-1]['day'])==cal[7]
 checks['native_cp_ratchet_then_old_line_exit_survives_confirmation']=True
 # A sale on the register-date OPEN owns zero at register CLOSE.
 event['record_date']=cal[2];s.BY_RECORD={cal[2]:[event]};s.closecache={}
 zz=run_campaign(s,base,r,'B',mp,{})
 assert not zz['claims'] and zz['campaign']['receivable']==0
 checks['record_day_open_sale_has_zero_close_entitlement']=True
 # Unadmitted split in an actually held path is UNKNOWN, not an invented share bridge.
 saved=s.unadmitted_action_at;s.unadmitted_action_at=lambda symbol,d:d==cal[2];s.closecache={}
 zz=run_campaign(s,base,r,'D',mp,{},nr,canonical)
 assert len(zz['actions'])==1 and 'UNADMITTED_ACTION' in zz['attempts'][0]['status']
 s.unadmitted_action_at=saved;checks['unadmitted_held_action_unknown_no_invented_shares']=True
 # Source/qualification UNKNOWN is retained; consumed CORE Q is irrelevant to flat CP.
 nr2={d:dict(v,event_Q=None) for d,v in nr.items()};s.closecache={}
 zz=run_campaign(s,base,r,'D',mp,{},nr2,canonical)
 assert len(zz['native_consumptions'])==3 and not zz['campaign']['native_unknown']
 checks['consumed_core_unknown_event_q_does_not_block_legal_cp']=True
 out=O/'SYNTHETIC_D_QA.json';assert not out.exists();out.write_text(json.dumps(dict(pass_all=all(checks.values()),checks=checks,hashes={p.name:sha(p) for p in [Path(__file__),O/'campaign_engine.py',O/'native_role_adapter.py']}),indent=2)+'\n');print(json.dumps(checks,indent=2))
if __name__=='__main__':main()
