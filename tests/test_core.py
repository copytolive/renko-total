from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from copytolive_renko import Tick, build_renko, floor_anchor, reversal_signals, backtest_signals
from copytolive_renko.metrics import summarize, monte_carlo

class CanonicalRenkoTests(unittest.TestCase):
    def tick(self,i,mid,spread=2):
        return Tick(i,1_700_000_000_000+i*1000,mid-spread//2,mid+spread//2)
    def test_floor_anchor(self):
        self.assertEqual(floor_anchor(203,10),200); self.assertEqual(floor_anchor(200,10),200)
    def test_inclusive_continuation(self):
        b=build_renko([self.tick(0,200),self.tick(1,210)],10)
        self.assertEqual(len(b),1); self.assertEqual((b[0].open_units,b[0].close_units),(200,210))
    def test_multi_brick_one_tick(self):
        b=build_renko([self.tick(0,200),self.tick(1,240)],10)
        self.assertEqual([x.close_units for x in b],[210,220,230,240]); self.assertTrue(all(x.source_tick_close==1 for x in b))
    def test_two_brick_reversal(self):
        b=build_renko([self.tick(0,200),self.tick(1,220),self.tick(2,200)],10)
        self.assertEqual([x.close_units for x in b],[210,220,200]); self.assertTrue(b[-1].is_reversal); self.assertEqual(b[-1].open_units,210)
    def test_anti_lookahead_entry_next_tick(self):
        ticks=[Tick(0,1000,199,201),Tick(1,2000,209,211),Tick(2,3000,210,212),Tick(3,4000,232,234)]
        trades=backtest_signals(ticks,reversal_signals(build_renko(ticks,10)),stop_units=10,take_units=20,price_unit=1.0,quantity_oz=1.0)
        self.assertEqual(len(trades),1); t=trades[0]
        self.assertEqual((t.signal_tick_id,t.entry_tick_id,t.entry_units,t.exit_units,t.exit_reason),(1,2,212,232,"TP"))
        self.assertEqual(t.pnl_price_units,20)
    def test_sell_uses_bid_entry_ask_exit(self):
        ticks=[Tick(0,1000,201,203),Tick(1,2000,189,191),Tick(2,3000,188,190),Tick(3,4000,166,168)]
        t=backtest_signals(ticks,reversal_signals(build_renko(ticks,10)),stop_units=10,take_units=20,price_unit=1.0,quantity_oz=1.0)[0]
        self.assertEqual((t.side,t.entry_units,t.exit_units,t.pnl_price_units),(-1,188,168,20))
    def test_metrics(self):
        ticks=[self.tick(i,x) for i,x in enumerate([200,210,220,200,190,180,200,210,220,200,190,180,200,210,220])]
        trades=backtest_signals(ticks,reversal_signals(build_renko(ticks,10)),stop_units=10,take_units=10,price_unit=1.0)
        self.assertEqual(summarize(trades)["total_entry"],len(trades)); self.assertEqual(monte_carlo(trades,iterations=20)["iterations"],20)

if __name__=="__main__": unittest.main()
