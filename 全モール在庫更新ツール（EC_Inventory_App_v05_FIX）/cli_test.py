from engine import precheck, run_all
from pathlib import Path
import argparse, json

p=argparse.ArgumentParser()
p.add_argument("--wholesale",required=True)
p.add_argument("--logiless",required=True)
p.add_argument("--ir-item")
p.add_argument("--ir-selection")
p.add_argument("--ir-itemsub")
p.add_argument("--amazon-report")
p.add_argument("--amazon-template")
p.add_argument("--mercari")
p.add_argument("--out",required=True)
args=p.parse_args()
inputs={
 "wholesale":args.wholesale,"logiless":args.logiless,
 "ir_item":args.ir_item or "","ir_selection":args.ir_selection or "","ir_itemsub":args.ir_itemsub or "",
 "amazon_report":args.amazon_report or "","amazon_template":args.amazon_template or "",
 "mercari":args.mercari or ""
}
channels=[]
if args.ir_item and args.ir_selection and args.ir_itemsub: channels.append("itemrobot")
if args.amazon_report and args.amazon_template: channels.append("amazon")
if args.mercari: channels.append("mercari")
print(json.dumps(run_all(inputs,args.out,channels),ensure_ascii=False,indent=2))
