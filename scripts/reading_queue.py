#!/usr/bin/env python3
"""Bridge a local agent to the durable reading queue. No model API requests."""
import argparse
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app import reading_queue,attention

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('list')
    sub.add_parser('shortlist')
    batch=sub.add_parser('screen-batch');batch.add_argument('assessments',type=Path)
    sub.add_parser('audit')
    sub.add_parser('plan')
    calibration=sub.add_parser('calibrate');calibration.add_argument('assessments',type=Path)
    screen=sub.add_parser('screen');screen.add_argument('item_id');screen.add_argument('--level',type=int,choices=[0,1,2],required=True);screen.add_argument('--reason',required=True);screen.add_argument('--quote',required=True)
    enqueue=sub.add_parser('enqueue');enqueue.add_argument('item_id')
    claim=sub.add_parser('claim');claim.add_argument('--task');claim.add_argument('--priority',action='store_true');claim.add_argument('--output',type=Path,required=True)
    for command in ['renew','release','submit']:
        child=sub.add_parser(command);child.add_argument('bundle',type=Path)
        if command=='submit':child.add_argument('report',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='list':print(json.dumps(reading_queue.snapshot(),ensure_ascii=False,indent=2))
        elif args.command=='shortlist':print(json.dumps(reading_queue.shortlist(),ensure_ascii=False,indent=2))
        elif args.command=='audit':print(json.dumps(reading_queue.audit(),ensure_ascii=False,indent=2))
        elif args.command=='plan':print(json.dumps(reading_queue.plan(),ensure_ascii=False,indent=2))
        elif args.command=='calibrate':
            attention.calibrate(json.loads(args.assessments.read_text()))
            print('已更新固定版本的重要性比较；全文报告与个人状态未改变。')
        elif args.command=='screen-batch':
            attention.assess_many(json.loads(args.assessments.read_text()))
            print('本批初筛已原子写入；仅调整精读顺序，未发布论文。')
        elif args.command=='screen':
            attention.assess(args.item_id,args.level,args.reason,args.quote)
            print('重要性初筛已记录；仅调整精读顺序，未发布论文。')
        elif args.command=='enqueue':print(reading_queue.enqueue(args.item_id))
        elif args.command=='claim':
            # Open exclusively before claiming, so an existing evidence bundle is never overwritten.
            fd=os.open(str(args.output),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            bundle=None
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as f:
                    bundle=reading_queue.claim_agent(args.task,priority_lane=args.priority)
                    f.write(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
            except Exception:
                if bundle:reading_queue.agent_action(bundle['task_id'],bundle['lease_token'],'release')
                args.output.unlink(missing_ok=True);raise
            print('已接手并保存公开原文证据包：'+str(args.output)+'；30分钟内提交，较久时请续租。')
        else:
            bundle=json.loads(args.bundle.read_text())
            report=json.loads(args.report.read_text()) if args.command=='submit' else None
            reading_queue.agent_action(bundle['task_id'],bundle['lease_token'],args.command,report)
            print('操作已完成；提交的研究判断仍需核查。')
    except (ValueError,KeyError,TypeError,OSError) as error:parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()
