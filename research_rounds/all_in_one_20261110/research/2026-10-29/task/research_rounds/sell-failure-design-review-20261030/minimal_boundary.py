"""Synthetic-only state machine; no market, account, or production imports."""
from dataclasses import dataclass,asdict
from math import exp,sqrt,isfinite

@dataclass
class BoundaryState:
    e0_floor: float
    warning_seen: bool=False
    warning_price: float|None=None
    warning_sigma: float|None=None
    boundary: float|None=None
    active: bool=False
    handed_off: bool=False
    unknown_scale: bool=False
    exit_locked: bool=False
    exit_reason: str|None=None
    exit_decision: int|None=None
    requests: int=0
    repeat_warnings_ignored: int=0
    observations: int=0

    def __post_init__(self):
        if not isfinite(self.e0_floor) or self.e0_floor<=0:
            raise ValueError('Original frozen E0 floor must be known and positive')

    def _lock(self,reason):
        self.exit_locked=True;self.exit_reason=reason
        self.exit_decision=self.observations;self.requests+=1

    def step(self,*,close,event=0,sigma=None,updated_e0_floor=None,original_exit=False):
        """At a synthetic close. Requests execute only at the next legal opportunity.

        Existing protection is checked before any same-day floor update.
        A newly created boundary becomes active for subsequent observations.
        """
        self.observations+=1
        if event not in (-1,0,1):raise ValueError('Native event must be -1,0,1')
        note='hold'
        stop_before=max(self.e0_floor,self.boundary) if self.active else self.e0_floor
        if self.exit_locked:
            note='exit_remains_locked'
        elif original_exit:
            self._lock('original_exit');note='original_exit_requested'
        elif close is None or not isfinite(close) or close<=0:
            note='price_unknown_preserve_state'
        elif close<=self.e0_floor:
            self._lock('original_floor');note='original_floor_requested'
        elif self.active and close<=self.boundary:
            self._lock('warning_boundary');note='boundary_exit_requested'
        else:
            if event==-1:
                if self.warning_seen:
                    self.repeat_warnings_ignored+=1;note='repeat_warning_ignored'
                else:
                    self.warning_seen=True;self.warning_price=close
                    if sigma is None or not isfinite(sigma) or sigma<=0:
                        self.unknown_scale=True;note='sigma_unknown_use_original_floor'
                    else:
                        b=close*exp(-sqrt(5)*sigma)
                        if not isfinite(b) or b<=0:
                            self.unknown_scale=True;note='boundary_numeric_unknown_use_original_floor'
                        else:
                            self.warning_sigma=sigma;self.boundary=b;self.active=True
                            note='first_warning_boundary_frozen'
            if updated_e0_floor is not None:
                if event!=1:raise ValueError('Test floor updates require native positive event')
                if not isfinite(updated_e0_floor) or updated_e0_floor<self.e0_floor:
                    raise ValueError('Original E0 floor may not decrease')
                self.e0_floor=updated_e0_floor
            if self.active and self.e0_floor>=self.boundary:
                self.active=False;self.handed_off=True;note='safe_handoff_to_original_floor'
            elif event==1 and self.active:
                note='positive_event_without_safe_floor_keep_boundary'
        stop_after=max(self.e0_floor,self.boundary) if self.active else self.e0_floor
        return dict(**asdict(self),close=close,event=event,note=note,
                    effective_stop_before=stop_before,effective_stop_after=stop_after,
                    earliest_execution='next_original_legal_execution' if self.exit_locked else None)
