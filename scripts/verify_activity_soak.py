"""Two-hour resource/operation soak on an explicitly labelled disposable desktop."""
import argparse
import json
from pathlib import Path
import subprocess
import time

SAMPLE = r'''
import json,pathlib,time,sqlite3
p=pathlib.Path('/sys/fs/cgroup')
def pairs(name):return dict((k,int(v)) for k,v in (line.split() for line in (p/name).read_text().splitlines()))
m=pairs('memory.stat');cpu=pairs('cpu.stat');e=pairs('memory.events')
meta=json.loads(pathlib.Path('/tmp/cyberlab-activity/owner.json').read_text());state=json.loads(pathlib.Path(meta['root'],'state.json').read_text())
with sqlite3.connect(pathlib.Path(meta['root'])/'events.sqlite3') as db:
 observed_events=db.execute('SELECT count(*) FROM events').fetchone()[0]
processes=[]
for d in pathlib.Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:
  cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if not any(part in cmd for part in ('cyberlab-activity/agent.py serve','cyberlab-activity/desktop.py','cyberlab-activity/emit.py')):continue
  if not cmd.startswith('/usr/bin/python3'):continue
  pss=next(int(l.split()[1])*1024 for l in (d/'smaps_rollup').read_text().splitlines() if l.startswith('Pss:'))
  processes.append({'pid':int(d.name),'pss_bytes':pss})
 except OSError:pass
print(json.dumps({'at':time.time(),'memory_bytes':int((p/'memory.current').read_text())-m.get('inactive_file',0),'memory_peak':int((p/'memory.peak').read_text()),'cpu_usec':cpu['usage_usec'],'pids':int((p/'pids.current').read_text()),'oom_kill':e['oom_kill'],'state':state,'observed_events':observed_events,'collector_processes':processes}))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--container', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=7200)
    args = parser.parse_args()
    container = json.loads(subprocess.check_output(['docker','inspect',args.container]))[0]
    assert container['Config']['Labels'].get('cyberlab.qa') == 'activity', 'Only disposable activity QA desktops are allowed'
    args.output.mkdir(parents=True, exist_ok=True)
    def execute(*command):
        return subprocess.check_output(['docker','exec',args.container,*command], text=True, timeout=25)
    def sample():
        return json.loads(subprocess.check_output(['docker','exec','-i',args.container,'python3','-'], input=SAMPLE, text=True, timeout=15))
    def focus(window):
        execute('xdotool','windowactivate','--sync',window)
        time.sleep(.2)
        assert execute('xdotool','getactivewindow').strip() == window, 'another application stole focus'
    def enter(window):
        # Never send Return to a first-run dialog that stole keyboard focus.
        assert execute('xdotool','getactivewindow').strip() == window, 'another application stole focus before submission'
        execute('xdotool','key','--clearmodifiers','Return')
    terminal = execute('xdotool','search','--onlyvisible','--name','^CyberLab-Activity-QA$').splitlines()[0]
    firefox = execute('xdotool','search','--onlyvisible','--name','Mozilla Firefox').splitlines()[0]
    started = time.monotonic()
    report = {'container':args.container,'image_id':container['Image'],'duration_target':args.seconds,'started_at':time.time(),'synthetic_qa':True,'passed':False}
    (args.output/'running.json').write_text(json.dumps(report))
    previous = None
    iteration = 0
    failure = None
    try:
        with (args.output/'samples.jsonl').open('a', buffering=1) as stream:
            while time.monotonic() - started < args.seconds:
                if iteration % 4 == 0:
                    focus(terminal)
                    execute('xdotool','key','--clearmodifiers','ctrl+u')
                    execute('xdotool','type','--clearmodifiers',f'printf CYBERLAB_SOAK_{iteration}')
                    enter(terminal)
                    time.sleep(1)
                elif iteration % 4 == 2:
                    focus(firefox)
                    execute('xdotool','key','--clearmodifiers','ctrl+l')
                    execute('xdotool','type','--clearmodifiers',f'http://127.0.0.1:8765/?soak={iteration}')
                    enter(firefox)
                    time.sleep(1)
                row = sample()
                if previous:
                    row['cpu_percent'] = (row['cpu_usec'] - previous['cpu_usec']) / ((row['at'] - previous['at']) * 10000)
                stream.write(json.dumps(row) + '\n')
                assert row['oom_kill'] == 0, 'OOM observed'
                assert row['state']['status'] == 'running', row['state']
                assert row['at'] - row['state']['heartbeat_at'] < 10, 'collector heartbeat stale'
                assert row['state']['providers']['desktop']['status'] == 'ready', row['state']['providers']
                if iteration % 4 == 0 and previous:
                    assert row['observed_events'] > previous['observed_events'], 'submitted command was not recorded'
                previous = row
                iteration += 1
                time.sleep(min(15, max(0, args.seconds - (time.monotonic() - started))))
        report['passed'] = True
    except Exception as exc:
        failure = str(exc)
        report['error'] = failure
    finally:
        rows = [json.loads(line) for line in (args.output/'samples.jsonl').read_text().splitlines()]
        report.update(duration_seconds=time.monotonic()-started, samples=len(rows), ended_at=time.time())
        if rows:
            report.update(peak_working_memory_mib=max(row['memory_bytes'] for row in rows)/1024**2,
                          peak_collector_pss_mib=max(sum(p['pss_bytes'] for p in row['collector_processes']) for row in rows)/1024**2,
                          final_memory_mib=rows[-1]['memory_bytes']/1024**2,
                          average_cpu_percent=(rows[-1]['cpu_usec']-rows[0]['cpu_usec'])/max(.001,(rows[-1]['at']-rows[0]['at']))/10000,
                          final_events=rows[-1]['observed_events'])
        (args.output/'result.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report),flush=True)
    if failure:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
