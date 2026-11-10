"""Historical-price/native-ledger matching-capacity fixture, not an economic arm."""
from pathlib import Path
from dataclasses import replace
import hashlib,json,time
import capacity_adapter as C
A,N,J,L,IO=C.A,C.N,C.J,C.L,C.IO
O=Path(__file__).resolve().parent


class FixtureAccount(C.GuardAccount):
    def fill_buy(self,sid,window):
        order=self.buys.get(sid)
        if not self.partial_fixture and order is not None and order.remaining_shares>200 and window.capacity_shares>=200:
            self.partial_fixture=True
            before=order.remaining_shares
            one=replace(window,capacity_shares=100,event_id=window.event_id+'|TECH_PART1',source_id=window.source_id+'|TECH_MATCHING_CAP100')
            r1=super().fill_buy(sid,one)
            assert r1 and r1.shares==100 and sid in self.buys
            remain1=self.buys[sid].remaining_shares
            two=replace(window,capacity_shares=100,event_id=window.event_id+'|TECH_PART2',source_id=window.source_id+'|TECH_MATCHING_CAP100')
            r2=super().fill_buy(sid,two)
            assert r2 and r2.shares==100
            self.partial_fixture_result=dict(sid=sid,at=window.at,original_submitted_cap=before,
                first_shares=r1.shares,first_actual_fee=r1.fees_cny,remaining_after_first=remain1,
                second_shares=r2.shares,second_actual_fee=r2.fees_cny,
                remaining_after_second=self.buys[sid].remaining_shares if sid in self.buys else 0,
                original_price_and_fee_model=True,only_matching_capacity_and_distinct_event_IDs_overridden=True)
            return r1
        return super().fill_buy(sid,window)


def main():
    out=O/'native-partial-fixture-v1'
    assert not(out/'STARTED.json').exists(),'never silently repeat fixture'
    out.mkdir(parents=True,exist_ok=True)
    files=[Path(__file__),O/'guard.py',O/'capacity_adapter.py']
    sources={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in files}
    IO.write_json(out/'STARTED.json',dict(scope='TECHNICAL_ONLY_NATIVE_TWO_PART_MATCHES_NOT_STRATEGY_PNL',sources=sources))
    N.configure_scores();old=A.S.O
    try:
        A.S.O=out/'input-readiness';shared,receipts,cp,states,ir,identity=A.S.inputs('2022')
    finally:A.S.O=old
    shared,receipts,kw=A.S.physical_inputs(shared,receipts,cp,states,ir,'2022-01-05')
    J.START,J.END='2022-01-01','2022-01-05'
    runner=C.Runner(shared,receipts,arms=['G20']);runner.source_freeze=sources
    a=runner.accounts['G20'];a.__class__=FixtureAccount;a.partial_fixture=False
    with IO.atomic_runner_outputs(runner,L,out,canonicalize=J.W.canon):
        assert runner.run_prepared(out,120,end=J.END)
    assert a.partial_fixture
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in sources.items())
    IO.write_gzip_jsonl(out/'pair/G20-cost-guard.jsonl.gz',a.capacity_events,encoder=J.C.encoded)
    IO.write_json(out/'ACTUAL_PARTIAL_PROOF.json',J.W.canon(dict(passed=True,scope='NATIVE_MATCHING_FIXTURE_NOT_ECONOMIC_RESULT',
        actual=a.partial_fixture_result,ending_cost_observer=a.capacity_basis,ending_entry_observer=a.capacity_entry,
        pending_at_end=len(a.buys),original_CASH_QTY_FEE_and_basis_postinvariants_passed=True)))
    print('NATIVE_PARTIAL_FIXTURE_COMPLETE',J.W.canon(a.partial_fixture_result),flush=True)


if __name__=='__main__':main()
