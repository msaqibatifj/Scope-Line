"""Run repeatable ScopeLine public checks and save evidence."""
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
import httpx
parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8000')
parser.add_argument('--output',default=str(Path(__file__).with_name('public_results.json')))
args=parser.parse_args()
cases=json.loads(Path(__file__).with_name('public_cases.json').read_text())
passed=0
records=[]
for case in cases:
    try:
        response=httpx.post(args.url.rstrip('/')+'/arena/run',json=case['request'],timeout=70)
        response.raise_for_status(); result=response.json()
        checks=[
            result['status']==case['expected_status'],
            result['stop_reason']==case['expected_stop_reason'],
        ]
        if 'expected_tool' in case:
            checks.append(any(call.get('tool')==case['expected_tool'] for call in result.get('tool_calls',[])))
        if 'expected_tool_outcome' in case:
            checks.append(any(call.get('outcome')==case['expected_tool_outcome'] for call in result.get('tool_calls',[])))
        if 'expected_event' in case:
            checks.append(any(event.get('event')==case['expected_event'] for event in result.get('events',[])))
        if 'expected_text' in case:
            checks.append(case['expected_text'] in result.get('final_response',''))
        ok=all(checks)
        if ok: passed+=1
        print(('PASS' if ok else 'FAIL')+' '+case['name'])
        records.append({'name':case['name'],'passed':ok,'status':result.get('status'),'stop_reason':result.get('stop_reason'),'steps':result.get('steps'),'tool_calls':result.get('tool_calls',[]),'errors':result.get('errors',[])})
    except (httpx.HTTPError,KeyError,ValueError) as exc:
        print('FAIL '+case['name']+' '+type(exc).__name__)
        records.append({'name':case['name'],'passed':False,'error_type':type(exc).__name__})
Path(args.output).write_text(json.dumps({'url':args.url,'generated_at':datetime.now(timezone.utc).isoformat(),'passed':passed,'total':len(cases),'cases':records},indent=2),encoding='utf-8')
print(f'{passed}/{len(cases)} checks passed. Results written to {args.output}.')
raise SystemExit(0 if passed==len(cases) else 1)
