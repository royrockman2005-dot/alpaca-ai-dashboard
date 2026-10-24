"""Point-in-time five-minute technical replay. Research only; no AI or broker orders.

Each decision uses only bars completed at the cutoff. Entry is next bar open.
OHLC ambiguity resolves against the strategy (stop before target).
"""
import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY=ZoneInfo("America/New_York")
COST_BPS_PER_SIDE=5
HOLD_BARS=6

def replay(rows,cutoff):
    if cutoff.tzinfo is None:
        raise ValueError("Cutoff must include timezone")
    rows=sorted(rows,key=lambda r:r[0])
    if len({r[0] for r in rows})!=len(rows):
        raise ValueError("Duplicate timestamps")
    for dt,op,hi,lo,cl in rows:
        if dt.tzinfo is None or not (0<lo<=min(op,cl)<=max(op,cl)<=hi):
            raise ValueError("Invalid bars")
    # Candle timestamp is its start; a 5m candle is available only 5m later.
    local_day=cutoff.astimezone(NY).date()
    def regular(r):
        local=r[0].astimezone(NY)
        return local.date()==local_day and 570<=local.hour*60+local.minute<960
    observed=[r for r in rows if regular(r) and r[0]+timedelta(minutes=5)<=cutoff]
    if len(observed)<21:
        return {"decision":"INSUFFICIENT_HISTORY","observed_bars":len(observed)}
    last=observed[-1]
    if cutoff-last[0]>timedelta(minutes=10):
        return {"decision":"STALE","observed_bars":len(observed)}
    if last[0].astimezone(NY).date()!=cutoff.astimezone(NY).date():
        return {"decision":"STALE","observed_bars":len(observed)}
    closes=[r[4] for r in observed]
    sma5=sum(closes[-5:])/5
    sma20=sum(closes[-20:])/20
    momentum=closes[-1]/closes[-6]-1
    decision="BUY" if sma5>sma20 and momentum>0 else "HOLD"
    result={"decision":decision,"observed_bars":len(observed),
            "cutoff_utc":cutoff.astimezone(timezone.utc).isoformat(),
            "signal_bar_utc":last[0].astimezone(timezone.utc).isoformat(),
            "reference_close":closes[-1],"sma5":round(sma5,5),
            "sma20":round(sma20,5),"momentum_25m_pct":round(momentum*100,4),
            "strategy":"fixed_sma5_sma20_momentum","research_only":True,
            "gemini_replayed":False}
    if decision=="HOLD":
        return result
    future=[r for r in rows if regular(r) and r[0]>=cutoff]
    if len(future)<HOLD_BARS:
        return {**result,"outcome":"INSUFFICIENT_FUTURE_BARS"}
    entry=future[0][1]
    # Fixed protective levels are predeclared, not fitted using future prices.
    stop=entry*.99
    target=entry*1.02
    price=future[HOLD_BARS-1][4]
    reason="time"
    for _,op,hi,lo,cl in future[:HOLD_BARS]:
        if op<=stop:
            price,reason=op,"stop_gap"
            break
        if op>=target:
            price,reason=target,"target_gap_conservative"
            break
        if lo<=stop:
            price,reason=stop,"stop"
            break
        if hi>=target:
            price,reason=target,"target"
            break
    net_pct=100*(price/entry-1-2*COST_BPS_PER_SIDE/10000)
    return {**result,"outcome":"EVALUATED","entry_utc":future[0][0].astimezone(timezone.utc).isoformat(),
            "entry":entry,"stop":stop,"target":target,"exit":price,
            "exit_reason":reason,"net_return_pct":round(net_pct,4),
            "profitable_after_costs":net_pct>0,
            "caveat":"Technical-only, fixed 5m candles; not a Gemini replay. No real execution or guaranteed stop fill."}

def load_csv(path):
    with Path(path).open(newline="",encoding="utf-8") as f:
        reader=csv.DictReader(f)
        return [(datetime.fromisoformat(r["timestamp"].replace("Z","+00:00")),
                 float(r["open"]),float(r["high"]),float(r["low"]),float(r["close"])) for r in reader]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",required=True)
    p.add_argument("--cutoff",required=True,help="ISO8601 timezone-aware cutoff")
    p.add_argument("--output",default="v6_reports/v67_replay.json")
    args=p.parse_args()
    result=replay(load_csv(args.csv),datetime.fromisoformat(args.cutoff.replace("Z","+00:00")))
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+"\\n")
    print(json.dumps(result,indent=2))
    print("NO ORDERS SUBMITTED")

if __name__=="__main__":
    main()
