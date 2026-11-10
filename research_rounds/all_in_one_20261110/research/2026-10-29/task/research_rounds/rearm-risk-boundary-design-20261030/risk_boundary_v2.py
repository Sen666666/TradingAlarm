"""Research-only lifecycle model. No market/account I/O or fill simulation."""
from dataclasses import dataclass
from math import isfinite,exp,sqrt

@dataclass(frozen=True)
class NegativeReceipt:
    event_id: str
    symbol: str
    source_id: str
    confirmed_bar: int
    native_code: int=-1

class RiskBoundary:
    def __init__(self,*,cycle_id,symbol,source_id,unit_id,shares,e0_floor,buy_pending=False):
        if not isinstance(shares,int) or shares<0:raise ValueError('Actual nonnegative shares required')
        if not isfinite(e0_floor) or e0_floor<=0:raise ValueError('Known original economic floor required')
        self.cycle_id=cycle_id;self.symbol=symbol;self.source_id=source_id;self.unit_id=unit_id
        self.shares=shares;self.shares_known=True;self.orders_known=True
        self.e0_floor=e0_floor;self.buy_pending=buy_pending;self.exit_order_pending=False
        self.phase='OBSERVING' if shares else 'NO_POSITION';self.ever_held=shares>0
        self.boundary=None;self.anchor=None;self.frozen_sigma=None;self.last_bar=None
        self.last_handoff_bar=-1;self.last_attempt_bar=None;self.seen=set()
        self.exit_locked=False;self.exit_reason=None;self.intent_count=0;self.episodes=0;self.issues=[]

    def effective_floor(self):
        return max(self.e0_floor,self.boundary) if self.boundary is not None else self.e0_floor

    def issue(self,label):
        self.issues.append(label)

    def sync_execution(self,*,shares,buy_pending,exit_order_pending):
        """Only an externally confirmed execution snapshot may change actual shares."""
        if shares is None:
            self.shares_known=False;self.issue('actual_shares_unknown');return
        if not isinstance(shares,int) or shares<0:raise ValueError('Invalid actual shares')
        if buy_pending is None or exit_order_pending is None:
            self.shares=shares;self.shares_known=True;self.orders_known=False
            self.issue('order_confirmation_unknown')
            if self.exit_locked:self.phase='EXIT_PENDING'
            elif shares>0 and self.phase=='NO_POSITION':self.phase='OBSERVING';self.ever_held=True
            elif shares>0 and self.phase=='CLOSED':self.issue('late_fill_after_closed_interface_gap');self._lock('late_fill_unresolved')
            return
        late=self.phase=='CLOSED' and shares>0
        self.shares=shares;self.shares_known=True;self.orders_known=True
        self.buy_pending=buy_pending;self.exit_order_pending=exit_order_pending
        if late:
            self.issue('late_fill_after_closed_interface_gap');self._lock('late_fill_unresolved')
        if self.exit_locked:
            self.phase='CLOSED' if shares==0 and not buy_pending and not exit_order_pending else 'EXIT_PENDING'
        elif shares>0:
            self.ever_held=True
            if self.phase in ['NO_POSITION','CLOSED']:self.phase='OBSERVING'
        else:
            self.phase='CLOSED' if self.ever_held and not buy_pending else 'NO_POSITION'

    def _lock(self,reason):
        if not self.exit_locked:self.exit_locked=True;self.exit_reason=reason;self.intent_count+=1
        self.phase='CLOSED' if self.shares_known and self.orders_known and not(self.shares or self.buy_pending or self.exit_order_pending) else 'EXIT_PENDING'

    def on_close(self,*,bar,raw_close,factor,unit_id,negative=None,sigma=None,
                 updated_floor=None,floor_known=True,event_feed_known=True,
                 direction_state=None,original_exit=False):
        before=self.effective_floor();note='hold';current_issues=[]
        def unknown(label):self.issue(label);current_issues.append(label)
        same_unit=unit_id==self.unit_id
        price=None
        if not same_unit:unknown('economic_unit_unknown')
        elif raw_close is None or factor is None or not isfinite(raw_close) or not isfinite(factor) or raw_close<=0 or factor<=0:
            unknown('price_or_factor_unknown')
        else:price=raw_close*factor
        if not event_feed_known:unknown('native_event_feed_unknown')
        duplicate=self.last_bar is not None and bar<=self.last_bar
        if original_exit and (self.shares>0 or self.buy_pending or not self.shares_known):
            self._lock('original_exit');note='original_exit_priority'
        elif self.exit_locked:
            note='exit_intent_remains_locked'
        elif not self.shares_known:
            note='actual_shares_unknown_preserve_responsibility'
            if price is not None and price<=self.effective_floor():
                self._lock('price_risk_with_unknown_actual_position');note='risk_locked_await_actual_shares'
        elif self.shares<=0:
            note='no_actual_position_no_risk_line'
        elif duplicate:
            note='duplicate_or_stale_close_no_rearm'
            if bar<self.last_bar:unknown('stale_close')
        else:
            self.last_bar=bar
            if price is not None and price<=self.e0_floor:
                self._lock('original_floor');note='original_floor_priority'
            elif price is not None and self.phase=='PROTECTED' and price<=self.boundary:
                self._lock('risk_boundary');note='boundary_exit_requested'
            else:
                if not floor_known:unknown('original_floor_update_unknown')
                elif updated_floor is not None:
                    if not same_unit:unknown('floor_unit_unknown')
                    elif not isfinite(updated_floor) or updated_floor<self.e0_floor:
                        unknown('invalid_floor_update_preserve_old')
                    elif price is not None and updated_floor>price:
                        unknown('floor_above_current_close_preserve_old')
                    else:self.e0_floor=updated_floor
                if self.phase=='PROTECTED' and self.e0_floor>=self.boundary:
                    self.phase='OBSERVING';self.last_handoff_bar=bar;note='safe_handoff_return_to_observation'
                if negative is not None:
                    valid=(event_feed_known and negative.native_code==-1 and negative.symbol==self.symbol
                           and negative.source_id==self.source_id and bool(negative.event_id))
                    if not valid:unknown('negative_receipt_identity_unknown')
                    elif negative.event_id in self.seen:note='duplicate_receipt_ignored'
                    else:
                        self.seen.add(negative.event_id)
                        if negative.confirmed_bar!=bar:unknown('stale_negative_receipt_not_replayed')
                        elif self.phase=='PROTECTED':note='active_boundary_frozen_new_receipt_consumed'
                        elif bar<=self.last_handoff_bar or self.last_attempt_bar==bar:
                            note='same_bar_handoff_or_attempt_no_rearm'
                        else:
                            self.last_attempt_bar=bar
                            if price is None:unknown('negative_anchor_price_unknown')
                            elif sigma is None or not isfinite(sigma) or sigma<=0:unknown('negative_sigma_unknown')
                            else:
                                candidate=price*exp(-sqrt(5)*sigma)
                                if not isfinite(candidate) or candidate<=0:unknown('candidate_boundary_numeric_unknown')
                                elif candidate<=self.e0_floor:note='candidate_dominated_by_original_floor'
                                else:
                                    self.boundary=candidate;self.anchor=price;self.frozen_sigma=sigma
                                    self.phase='PROTECTED';self.episodes+=1;note='independent_negative_rearmed'
        after=self.effective_floor()
        # A pending exit never deletes the audit boundary or relaxes protection.
        assert after>=before,'Protection must not decrease in fixed economic units'
        return dict(cycle_id=self.cycle_id,bar=bar,phase=self.phase,shares=self.shares,
                    buy_pending=self.buy_pending,exit_order_pending=self.exit_order_pending,
                    boundary=self.boundary,anchor=self.anchor,sigma=self.frozen_sigma,
                    e0_floor=self.e0_floor,protection_before=before,protection_after=after,
                    economic_close=price,direction_state=direction_state,note=note,
                    exit_locked=self.exit_locked,exit_reason=self.exit_reason,intent_count=self.intent_count,
                    desired_cancel_buy=bool(self.exit_locked and self.buy_pending),
                    desired_submit_exit=bool(self.exit_locked and self.shares>0 and not self.exit_order_pending and self.shares_known and self.orders_known),
                    execution_status_refresh_required=not(self.shares_known and self.orders_known),
                    actual_holding_responsibility=self.shares>0 or not self.shares_known,episodes=self.episodes,
                    seen_receipts=len(self.seen),current_unknown=current_issues,all_unknown=list(self.issues))
