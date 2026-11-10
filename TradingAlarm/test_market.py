import json
import unittest
from datetime import datetime
from pathlib import Path
from market import EVIDENCE, decode, frames, minute_stamp, minutes, bars

class MarketTests(unittest.TestCase):
    def test_independent_probe_matches_saved_result(self):
        expected=json.loads((EVIDENCE/'session-decoded.json').read_text())
        for kind in (200,210):
            result=decode(next(frames((EVIDENCE/f'session-response-{kind}.bin').read_bytes())))
            self.assertEqual(result[0],kind)
            self.assertEqual(result[2],expected[str(kind)]['records'])

    def test_packed_intraday_calendar(self):
        self.assertEqual(minute_stamp(int.from_bytes(bytes.fromhex('5e82ea07'),'little')),('2026-10-16','09:30'))
        self.assertEqual(minute_stamp(int.from_bytes(bytes.fromhex('7983ea07'),'little')),('2026-10-16','13:57'))

    def test_cumulative_volume_differencing_missing_and_reset(self):
        def packed(day,minute):return (126<<20)|(10<<16)|(day<<11)|(9<<6)|minute
        rows=minutes([{'1':packed(16,30),'10':10,'13':100,'19':1000},
                      {'1':packed(16,31),'10':11,'13':160,'19':1660},
                      {'1':packed(16,32),'10':11,'13':None,'19':None},
                      {'1':packed(16,33),'10':11,'13':200,'19':2100},
                      {'1':packed(17,30),'10':12,'13':20,'19':240}])
        self.assertEqual([r['volume'] for r in rows],[100,60,None,None,20])
        self.assertEqual([r['amount'] for r in rows],[1000,660,None,None,240])

    def test_reject_incomplete_frame(self):
        with self.assertRaises(ValueError):list(frames(b'\xfd'*4+b'00000009'+b'\x09'+b'abc'))

    def test_app_dataset_invariants(self):
        data=json.loads((Path(__file__).parent/'data/market.json').read_text())
        self.assertGreater(len(data['stocks']),1000)
        symbols=set()
        for stock in data['stocks']:
            self.assertNotIn(stock['symbol'],symbols);symbols.add(stock['symbol'])
            dates=[r['date'] for r in stock['bars']]
            self.assertEqual(dates,sorted(set(dates)))
            for r in stock['bars']:
                datetime.strptime(r['date'],'%Y-%m-%d')
                self.assertLessEqual(r['low'],min(r['open'],r['close']))
                self.assertGreaterEqual(r['high'],max(r['open'],r['close']))
            for r in stock['intraday']:
                datetime.strptime(r['date']+' '+r['time'],'%Y-%m-%d %H:%M')
                if r['volume'] is not None:self.assertGreaterEqual(r['volume'],0)
        text=json.dumps(data)
        self.assertNotIn('passport64',text)
        self.assertNotIn('UserName',text)

if __name__=='__main__':unittest.main()
