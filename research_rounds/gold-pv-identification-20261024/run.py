from pathlib import Path
import datetime, hashlib, importlib.util, json
import numpy as np
import pandas as pd
from models import configurations, features, simulate, add_progress

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=HERE.parent/'gold-chart-fit-20261024'
INFER=HERE.parent/'gold-temperature-inference-20261024'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,(np.integer,np.bool_)):return x.item()
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x
def dump(p,x):Path(p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def reference(d):
    idx=d.loc['2025-01-02':'2026-10-13'].index
    raw=json.loads((INFER/'refined-targets.json').read_text())['points'];points=[]
    truth=np.zeros(len(idx),int);known=np.ones(len(idx),bool)
    for t in raw:
        t=dict(t);t['index']=idx.get_loc(t['date']);t['lo']=idx.get_loc(t['earliest']);t['hi']=idx.get_loc(t['latest']);points.append(t)
        known[t['lo']:t['hi']+1]=False
    for a,b in zip(points[::2],points[1::2]):truth[a['index']:b['index']]=1
    return idx,points,truth,known

def event_match(pred,refs,penalty=30):
    n,m=len(pred),len(refs);cost=np.full((n+1,m+1),np.inf);cost[:,0]=np.arange(n+1)*penalty;cost[0,:]=np.arange(m+1)*penalty;back={}
    for i in range(1,n+1):back[i,0]='extra'
    for j in range(1,m+1):back[0,j]='missing'
    for i,(pi,kind) in enumerate(pred,1):
      for j,t in enumerate(refs,1):
        distance=max(t['lo']-pi,0,pi-t['hi']) if kind==t['kind'] else np.inf
        cost[i,j],back[i,j]=min([(cost[i-1,j-1]+distance,'match'),(cost[i-1,j]+penalty,'extra'),(cost[i,j-1]+penalty,'missing')],key=lambda x:x[0])
    rows=[];i=n;j=m
    while i or j:
        action=back[i,j]
        if action=='match':
            pi,kind=pred[i-1];t=refs[j-1];rows.append(dict(action=action,kind=kind,predicted_index=pi,target_id=t['id'],target_index=t['index'],offset=pi-t['index'],outside_band=max(t['lo']-pi,0,pi-t['hi'])));i-=1;j-=1
        elif action=='extra':
            pi,kind=pred[i-1];rows.append(dict(action=action,kind=kind,predicted_index=pi));i-=1
        else:
            t=refs[j-1];rows.append(dict(action=action,kind=t['kind'],target_id=t['id'],target_index=t['index']));j-=1
    return float(cost[n,m]),rows[::-1]

def evaluate(state,idx,points,truth,known,blocks=None):
    z=state.reindex(idx);active=z.target.to_numpy(dtype=int)
    events=sorted([(int(i),'start') for i in np.flatnonzero(z.entered.to_numpy())]+[(int(i),'end') for i in np.flatnonzero(z.exited.to_numpy())])
    blocks=[(0,len(idx))] if blocks is None else blocks
    mask=np.zeros(len(idx),bool);rows=[];cost=0.;nref=0
    for low,high in blocks:
        mask[low:high]=True;rr=[t for t in points if low<=t['index']<high];pp=[t for t in events if low<=t[0]<high]
        cc,mm=event_match(pp,rr);cost+=cc;nref+=len(rr);rows+=mm
    usable=mask&known;mismatch=float(np.mean(active[usable]!=truth[usable])) if usable.any() else 0.
    matched=[x for x in rows if x['action']=='match'];extras=sum(x['action']=='extra' for x in rows);missing=sum(x['action']=='missing' for x in rows)
    out=dict(score=.5*mismatch+.5*cost/(30*max(1,nref)),state_mismatch=mismatch,event_cost=cost,reference_events=nref,
        starts=sum(low<=i<high and k=='start' for i,k in events for low,high in blocks),ends=sum(low<=i<high and k=='end' for i,k in events for low,high in blocks),
        active_days=int(active[mask].sum()),known_state_days=int(usable.sum()),matched=len(matched),within_band=sum(x['outside_band']==0 for x in matched),extras=extras,missing=missing,
        mean_abs_offset=float(np.mean([abs(x['offset']) for x in matched])) if matched else None,
        august10_active=int(z.loc['2026-08-10','target']) if '2026-08-10' in z.index else None,
        apr_oct_2026_active=int(z.loc['2026-04-01':,'target'].sum()))
    return out,rows

def load_controls(d):
    controls={}
    for p in sorted((OLD/'results/v0/daily').glob('*.parquet')):
        z=pd.read_parquet(p)[['target','entered','exited','floor']].reindex(d.index)
        assert not z[['target','entered','exited']].isna().any().any()
        controls['old:'+p.stem]=z
    tri=pd.read_parquet(HERE.parent/'three-layer-prototype-20261024/results/v0/daily/AU0.parquet')
    for col in ['open','high','low','close','volume']:np.testing.assert_array_equal(d[col],tri[col])
    controls['old:three_layer']=tri[['new_target','new_entered','new_exited','new_floor']].rename(columns=lambda x:x[4:])
    return controls

def stage_calibration(d,states,names,idx,out):
    spec=importlib.util.spec_from_file_location('prior_threshold_fit',INFER/'calibrate.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    labels=pd.read_csv(INFER/'measured-daily.csv',index_col='date',parse_dates=True)
    good=labels.index[labels.known.eq(1)&labels.level.gt(0)];y=labels.loc[good,'level'].astype(int)
    refs=json.loads((INFER/'refined-targets.json').read_text())['points'];pairs=pd.Series(0,index=good)
    for pair,(a,b) in enumerate(zip(refs[::2],refs[1::2]),1):pairs.loc[(good>=a['date'])&(good<b['date'])]=pair
    assert len(good)==68 and pairs.gt(0).all()
    scores=[];fits={};preds={};folds=[]
    for name in names:
        state=states[name]
        if 'normalized_peak' not in state:state=add_progress(d,state);states[name]=state
        for feature in ['advance','peak_advance','normalized_peak','volume_peak']:
            x=state.reindex(good)[feature];valid=x.notna()&state.reindex(good).target.eq(1)
            if valid.sum()<4:continue
            fit=mod.fit_thresholds(x[valid].to_numpy(),y[valid].to_numpy());key=name+'|'+feature;fits[key]=fit
            prediction=pd.Series(0,index=d.index,dtype=int);xx=state[feature];ok=xx.notna()&state.target.eq(1)
            prediction.loc[ok]=mod.predict(xx[ok].to_numpy(),fit)
            pp=prediction.reindex(good);score=mod.metrics(y.to_numpy(),pp.to_numpy())
            scores.append(dict(model=name,feature=feature,split='all_visible',active_color_rows=int(valid.sum()),**score));preds[key]=prediction
            fold_predictions=pd.Series(0,index=good,dtype=int)
            for pair in range(1,6):
                train=(pairs!=pair)&valid;test=pairs==pair
                if train.sum()<2:continue
                ff=mod.fit_thresholds(x[train].to_numpy(),y[train].to_numpy());vv=test&valid
                fold_predictions.loc[vv]=mod.predict(x[vv].to_numpy(),ff)
                missing_classes=sorted(set(y[test])-set(y[train]))
                folds.append(dict(model=name,feature=feature,held_pair=pair,missing_training_classes=','.join(map(str,missing_classes)),**mod.metrics(y[test].to_numpy(),fold_predictions[test].to_numpy())))
            scores.append(dict(model=name,feature=feature,split='leave_episode',active_color_rows=int(valid.sum()),**mod.metrics(y.to_numpy(),fold_predictions.to_numpy())))
    frame=pd.DataFrame(scores).sort_values(['split','balanced_mae','mae','model','feature']);frame.to_csv(out/'stage-scores.csv',index=False)
    pd.DataFrame(folds).to_csv(out/'stage-folds.csv',index=False);dump(out/'stage-thresholds.json',fits)
    pred=pd.DataFrame(preds);pred.to_parquet(out/'stage-predictions.parquet')
    return frame,fits,pred

def main():
    freeze=json.loads((HERE/'freeze.json').read_text())
    for p,h in freeze['hashes'].items():assert sha(ROOT/p)==h,(p,'changed input/code')
    cfgs=freeze['configurations'];out=HERE/'results/v0';out.mkdir(parents=True,exist_ok=False);(out/'daily').mkdir()
    d=pd.read_csv(OLD/'data/sina-AU0.csv',index_col='date',parse_dates=True);idx,points,truth,known=reference(d)
    f=features(d);f.to_parquet(out/'features.parquet');states=load_controls(d);configs={x['id']:x for x in cfgs}
    for cfg in cfgs:states[cfg['id']]=simulate(d,cfg,f)
    split=idx.searchsorted(pd.Timestamp('2025-09-01'));boundaries=[0]+[(points[i]['index']+points[i+1]['index'])//2 for i in [1,3,5,7]]+[len(idx)]
    folds=list(zip(boundaries[:-1],boundaries[1:]));scores=[];matches=[]
    for name,state in states.items():
        cfg=configs.get(name,{});group='old' if name.startswith('old:') else 'new'
        for part,blocks in [('all',None),('early',[(0,split)]),('late',[(split,len(idx))])]:
            sc,mt=evaluate(state,idx,points,truth,known,blocks)
            scores.append(dict(model=name,group=group,family=cfg.get('family','old'),volume=cfg.get('volume','old'),memory=cfg.get('memory','old'),split=part,**sc))
            if part=='all':matches.extend([dict(model=name,**x) for x in mt])
        if group=='new':
          for j in range(5):
            for part,blocks in [('train',[b for k,b in enumerate(folds) if k!=j]),('test',[folds[j]])]:
                sc,_=evaluate(state,idx,points,truth,known,blocks);scores.append(dict(model=name,group=group,family=cfg['family'],volume=cfg['volume'],memory=cfg['memory'],split=f'fold{j+1}_{part}',**sc))
    ranking=pd.DataFrame(scores).sort_values(['split','score','model']);ranking.to_csv(out/'ranking-all-splits.csv',index=False)
    ranking.loc[ranking.split.eq('all')].to_csv(out/'ranking.csv',index=False)
    matchframe=pd.DataFrame(matches)
    for col in ['predicted_index','target_index']:
        matchframe[col.replace('index','date')]=matchframe[col].map(lambda v:str(idx[int(v)].date()) if pd.notna(v) else None)
    matchframe.to_csv(out/'event-matches.csv',index=False)
    selection=[]
    for train,test in [('early','late')]+[(f'fold{i}_train',f'fold{i}_test') for i in range(1,6)]:
        for volume in ['P','PV']:
            winner=ranking.loc[ranking.split.eq(train)&ranking.group.eq('new')&ranking.volume.eq(volume)].iloc[0]
            testrow=ranking.loc[ranking.split.eq(test)&ranking.model.eq(winner.model)].iloc[0]
            selection.append(dict(selection_split=train,evaluation_split=test,volume=volume,model=winner.model,training_score=winner.score,**{k:testrow[k] for k in ['score','state_mismatch','event_cost','reference_events','within_band','extras','missing','active_days']}))
    pd.DataFrame(selection).to_csv(out/'transfer-selection.csv',index=False)
    full=ranking.loc[ranking.split.eq('all')];new=full.loc[full.group.eq('new')];old=full.loc[full.group.eq('old')]
    familybest=new.groupby(['family','volume'],sort=False).head(1);familybest.to_csv(out/'family-best.csv',index=False)
    selected=list(dict.fromkeys(familybest.model.tolist()+new.head(3).model.tolist()+[x['model'] for x in selection]+old.head(2).model.tolist()+['old:original','old:temperature_entry4','old:three_layer']))
    stage_scores,stage_fits,stagepred=stage_calibration(d,states,selected,idx,out)
    for name in selected:states[name].join(d,rsuffix='_bar').to_parquet(out/'daily'/(name.replace(':','_')+'.parquet'))
    # All candidate histories retained, including weak and losing fits.
    np.savez_compressed(out/'all-states.npz',models=np.array(list(states)),dates=np.array(d.index.strftime('%Y-%m-%d')),target=np.stack([z.target.to_numpy(dtype=np.int8) for z in states.values()]),entered=np.stack([z.entered.to_numpy(dtype=np.int8) for z in states.values()]),exited=np.stack([z.exited.to_numpy(dtype=np.int8) for z in states.values()]))
    # Paired P/PV comparison: identical mechanism/parameters, actual volume only.
    pairs=[]
    for cfg in cfgs:
        if cfg['volume']!='PV':continue
        pc=dict(cfg,volume='P',id=cfg['id'].replace('-PV-','-P-'));pn=pc['id'];a=full.loc[full.model.eq(cfg['id'])].iloc[0];b=full.loc[full.model.eq(pn)].iloc[0]
        z=states[cfg['id']].reindex(idx);zz=states[pn].reindex(idx)
        pairs.append(dict(model=cfg['id'],price_control=pn,score=a.score,price_score=b.score,delta_score=a.score-b.score,changed_days=int(z.target.ne(zz.target).sum()),changed_entries=int(z.entered.ne(zz.entered).sum()),changed_exits=int(z.exited.ne(zz.exited).sum())))
    pd.DataFrame(pairs).to_csv(out/'volume-pairs.csv',index=False)
    # Meaningful fixed-parameter causality, quantity counterfactual and quote sensitivity.
    checks=[];sensitivity=[];counter=[]
    checknames=list(dict.fromkeys(familybest.model.tolist()+[x['model'] for x in selection]+new.head(3).model.tolist()))
    for date in ['2025-02-28','2025-04-10','2025-09-01','2025-10-22','2026-01-30','2026-08-10','2026-10-23']:
        short=d.loc[:date];ff=features(short)
        pd.testing.assert_frame_equal(ff,f.loc[:date],check_freq=False)
        for name in checknames:
            zz=simulate(short,configs[name],ff);pd.testing.assert_frame_equal(zz,states[name].loc[:date],check_freq=False);checks.append(dict(model=name,cutoff=date,rows=len(short),passed=True))
    flat=d.copy();flat['volume']=1.;ff=features(flat)
    for name in checknames:
        cfg=configs[name]
        if cfg['volume']!='PV':continue
        z=simulate(flat,cfg,ff);pc=dict(cfg,volume='P');pp=simulate(d,pc,f)
        for col in ['target','entered','exited']:np.testing.assert_array_equal(z[col],pp[col])
        oldstate=states[name];counter.append(dict(model=name,constant_volume_equals_price_state=True,original_vs_flat_changed_days=int(z.loc[idx,'target'].ne(oldstate.loc[idx,'target']).sum())))
    for amplitude in [-.0025,.0025]:
        # Smooth unknown roll/index-construction perturbation; deterministic, no labels.
        dd=d.copy();factor=np.exp(amplitude*np.sin(np.arange(len(d))*2*np.pi/63))
        for col in ['open','high','low','close']:dd[col]*=factor
        ff=features(dd)
        for name in checknames:
            zz=simulate(dd,configs[name],ff);sc,_=evaluate(zz,idx,points,truth,known);sensitivity.append(dict(model=name,price_perturbation=amplitude,**sc))
    pd.DataFrame(sensitivity).to_csv(out/'quote-sensitivity.csv',index=False)
    dump(out/'checks.json',dict(prefix=checks,constant_volume=counter,meaning='Fixed parameters are causal; full-history parameter/grade calibration is retrospective. Does not certify proprietary source labels were causal.'))
    # Exact blue-point data table and frozen reference state for transparent review.
    dump(out/'reference.json',dict(points=points,folds=folds,split_index=int(split),evaluation_first=str(idx[0].date()),evaluation_last=str(idx[-1].date())))
    pd.DataFrame(dict(date=idx,reference_rightside=truth,known_state=known)).to_csv(out/'reference-state.csv',index=False)
    summary=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),freeze_sha256=sha(HERE/'freeze.json'),configurations=len(cfgs),new_price_volume_configurations=sum(x['volume']=='PV' for x in cfgs),old_controls=len(old),selected_stage_models=selected,
        best_full=new.head(8).to_dict('records'),best_families=familybest.to_dict('records'),old_comparison=old.to_dict('records'),transfer_selection=selection,
        best_stage_full=stage_scores.loc[stage_scores.split.eq('all_visible')].head(8).to_dict('records'),best_stage_omitted=stage_scores.loc[stage_scores.split.eq('leave_episode')].head(8).to_dict('records'),
        prefix_checks=len(checks),volume_counterfactuals=len(counter),accounts=0,wechat_operations=0,market_requests=0,post_result_mechanism_revisions=0,
        limits=['All inputs/images already seen development material; no out-of-sample claim.','AU0 input not proven identical to source index price; only two printed month/day anchors.','No seventh-state daily labels or source formula; four summer colors are pixel estimates.'])
    dump(out/'complete.json',summary)
    print(new.head(12)[['model','score','state_mismatch','within_band','extras','missing','active_days']].to_string(index=False))
    print('TRANSFER',pd.DataFrame(selection).head(2).to_json(orient='records',force_ascii=False))
    print('STAGES',stage_scores.loc[stage_scores.split.eq('all_visible')].head(6).to_json(orient='records',force_ascii=False))

if __name__=='__main__':main()
