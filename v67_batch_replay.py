"""Batch historical replay without look-ahead; research only."""
import argparse
import csv
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from statistics import mean
from v67_point_in_time import load_csv,replay

def batch_replay(rows,step=6):
    if step<1:raise ValueError("step must be >=1")
    rows=sorted(rows,key=lambda r:r[0])
    results=[]
    # Each candidate cutoff is after a completed 5-minute bar. Non-overlap
    # decisions reduce but do not eliminate statistical dependence.
    for i in range(21,len(rows)-6,step):
        cutoff=rows[i][0]+timedelta(minutes=5)
        result=replay(rows,cutoff)
        if result.get("decision") in ("BUY","HOLD"):
            results.append(result)
    return results

def summary(results):
    decisions=Counter(r.get("decision") for r in results)
    evaluated=[r for r in results if r.get("outcome")=="EVALUATED"]
    values=[r["net_return_pct"] for r in evaluated]
    if values:
        wins=sum(x>0 for x in values)
        profit=sum(max(0,x) for x in values)
        loss=-sum(min(0,x) for x in values)
        equity=peak=1.0
        drawdown=0.0
        for x in values:
            equity*=1+x/100
            peak=max(peak,equity)
            drawdown=min(drawdown,equity/peak-1)
    return {"cutoffs":len(results),"buy_decisions":decisions["BUY"],
            "hold_decisions":decisions["HOLD"],"evaluated_buys":len(values),
            "win_rate_pct":round(100*wins/len(values),2) if values else None,
            "avg_net_pct":round(mean(values),4) if values else None,
            "profit_factor":round(profit/loss,3) if values and loss else None,
            "max_sequential_drawdown_pct":round(100*drawdown,3) if values else None,
            "research_only":True,
            "caveats":"Fixed technical rule, not Gemini; no portfolio sizing, order latency or true historical news; non-independent overlapping market regimes; no claims of future returns."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",required=True)
    p.add_argument("--step",type=int,default=6)
    p.add_argument("--output",default="v6_reports/v67_batch_summary.json")
    args=p.parse_args()
    results=batch_replay(load_csv(args.csv),args.step)
    report=summary(results)
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    with out.with_name("v67_batch_decisions.csv").open("w",newline="",encoding="utf-8") as f:
        keys=["cutoff_utc","decision","outcome","entry","exit","exit_reason","net_return_pct"]
        writer=csv.DictWriter(f,fieldnames=keys)
        writer.writeheader()
        writer.writerows([{k:r.get(k) for k in keys} for r in results])
    print(json.dumps(report,indent=2))
    print("NO ORDERS SUBMITTED")

if __name__=="__main__":main()
