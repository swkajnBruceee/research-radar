#!/usr/bin/env python3
"""Import a single agent draft, with exact source and citation validation. No API calls."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app import deep_read

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    args=parser.parse_args()
    try:
        digest=deep_read.import_agent_report(json.loads(args.report.read_text()))
    except (ValueError,KeyError,TypeError) as error:
        parser.exit(1,str(error)+'\n')
    print('代理精读草稿已保存；原文 '+digest[:12]+'；个人笔记未改动。')
