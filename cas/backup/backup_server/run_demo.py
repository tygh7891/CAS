#!/usr/bin/env python3
"""A3 simulation with optional independent read-only real robot1 telemetry."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
from engine import Coordinator

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--live-robot1',action='store_true',help='subscribe to real domain14; no movement command')
parser.add_argument('--cancel-after',type=float,help='cancel simulation after N seconds for a visible cancellation test')
args=parser.parse_args()
if args.cancel_after is not None and args.cancel_after<=0:parser.error('cancel-after must be positive')
config=json.loads((ROOT/'scenario.mock.json').read_text())
coordinator=Coordinator(config)
logdir=ROOT/'logs';logdir.mkdir(exist_ok=True)
logpath=logdir/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.jsonl')
reader=None
messages=queue.Queue()
latest=None
latest_at=0.0

def read(pipe,is_error=False):
    for line in pipe:
        try:messages.put(('error',line.strip()) if is_error else ('data',json.loads(line)))
        except ValueError:messages.put(('error',line.strip()))

def show_live():
    if reader is None:return
    if latest is None or time.monotonic()-latest_at>3:
        print('[REAL robot_1 READ ONLY] no fresh receiver report; simulated robot_1 is separate',flush=True)
    else:
        print('[REAL robot_1 READ ONLY] '+json.dumps(latest,ensure_ascii=False),flush=True)

print('CAS A3 | BOTH TASKS ARE SIMULATED; real robot1 is telemetry only',flush=True)
print('Mock coordinates are unrelated to the real map. No motor or Nav2 commands are sent.',flush=True)
print('Log: '+str(logpath),flush=True)
try:
    if args.live_robot1:
        reader=subprocess.Popen([sys.executable,str(ROOT/'live_reader.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        for pipe,error in [(reader.stdout,False),(reader.stderr,True)]:
            threading.Thread(target=read,args=(pipe,error),daemon=True).start()
    with logpath.open('w') as log:
        cursor=0;start=time.monotonic();next_status=0.0
        while not coordinator.finished:
            time.sleep(0.05)
            coordinator.tick(0.05)
            if args.cancel_after is not None and time.monotonic()-start>=args.cancel_after:
                coordinator.cancel_all()
            while True:
                try:kind,item=messages.get_nowait()
                except queue.Empty:break
                if kind=='data':
                    latest=item;latest_at=time.monotonic()
                    log.write(json.dumps(dict(event='REAL_TELEMETRY',wall_time=datetime.now().isoformat(),payload=item),ensure_ascii=False)+'\n')
                else:print('[REAL receiver] '+item,flush=True)
            for event in coordinator.events[cursor:]:
                print('[SIM] '+json.dumps(event,ensure_ascii=False),flush=True)
                log.write(json.dumps(dict(event,wall_time=datetime.now().isoformat()),ensure_ascii=False)+'\n')
            cursor=len(coordinator.events)
            if time.monotonic()>=next_status:
                print('[SIM STATUS] '+json.dumps(coordinator.snapshot(),ensure_ascii=False),flush=True)
                show_live();next_status=time.monotonic()+1
            log.flush()
        final=coordinator.snapshot()
        log.write(json.dumps(dict(event='FINAL',payload=final),ensure_ascii=False)+'\n')
        print('[SIM FINAL] '+json.dumps(final,ensure_ascii=False),flush=True)
        show_live()
        if args.live_robot1 and (latest is None or latest.get('status')!='RECEIVING' or time.monotonic()-latest_at>3):
            print('REAL telemetry NOT verified. Simulation result does not prove robot connectivity.',flush=True)
        print('SIMULATION COMPLETED' if all(r['task_state']=='SUCCEEDED' for r in final['robots']) else 'SIMULATION HALTED',flush=True)
except KeyboardInterrupt:
    coordinator.cancel_all()
    with logpath.open('a') as log:log.write(json.dumps(dict(event='USER_CANCELED',payload=coordinator.snapshot()),ensure_ascii=False)+'\n')
    print('Simulation canceled; real robot was never commanded.',flush=True)
finally:
    if reader is not None and reader.poll() is None:
        os.killpg(reader.pid,signal.SIGINT)
        try:reader.wait(timeout=4)
        except subprocess.TimeoutExpired:reader.kill();reader.wait()
