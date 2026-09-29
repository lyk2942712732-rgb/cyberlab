"""Explicit QA workload for a disposable Kali container, never auto-started."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import uuid

from agent import request


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def wait_for(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except Exception:
            pass
        time.sleep(.2)
    raise AssertionError('condition timed out')


def events():
    meta = json.loads(Path('/tmp/cyberlab-activity/owner.json').read_text())
    with sqlite3.connect(Path(meta['root']) / 'events.sqlite3') as db:
        return [dict(type=t, source=s, data=json.loads(d)) for t,s,d in db.execute('SELECT type,source,data FROM events ORDER BY seq')]


def find_event(kind, value):
    return next((e for e in events() if e['type'] == kind and value in json.dumps(e['data'], ensure_ascii=False)), None)


def type_text(value):
    run('xdotool', 'type', '--clearmodifiers', '--delay', '10', value)


def key(value):
    run('xdotool', 'key', '--clearmodifiers', value)


def main():
    os.environ['DISPLAY'] = ':1'
    os.environ.update(json.loads(Path('/tmp/runtime-student/desktop-env.json').read_text()))
    session = str(uuid.uuid4())
    subprocess.run(['/usr/bin/python3', str(Path(__file__).with_name('agent.py')), 'start', session, '1', '64'], check=True)
    subprocess.Popen(['xfce4-terminal', '--disable-server', '--title=CyberLab-Activity-QA'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    terminal = wait_for(lambda: run('xdotool', 'search', '--onlyvisible', '--name', '^CyberLab-Activity-QA$').splitlines()[0])
    run('xdotool', 'windowactivate', '--sync', terminal)
    time.sleep(.5)
    type_text('printf WRONG')
    key('ctrl+u')
    type_text('printf CYBERLAB_FINAL_COMMAND')
    key('Return')
    wait_for(lambda: find_event('terminal.submit', 'CYBERLAB_FINAL_COMMAND'))
    assert not find_event('terminal.submit', 'WRONG')
    type_text("printf 'MULTI\nLINE'")
    key('Return')
    wait_for(lambda: find_event('terminal.submit', 'MULTI'))
    key('Up'); key('Return')
    wait_for(lambda: len([e for e in events() if e['type']=='terminal.submit' and 'MULTI' in e['data']['command']]) == 2)

    webroot = Path('/tmp/activity-qa-web'); webroot.mkdir(exist_ok=True)
    (webroot/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>CyberLab Activity QA</title>
<style>body{font:24px sans-serif;padding:40px}input,button{font:inherit;display:block;margin:16px}</style>
<form action="/done" method="get"><label>Answer<input autofocus name="answer"></label>
<label>Password<input type="password" name="password"></label><button id="send">提交实验</button></form>
<script>document.querySelector('form').addEventListener('submit',e=>{e.preventDefault();document.title='SUBMITTED'})</script>''', encoding='utf-8')
    server = subprocess.Popen(['/usr/bin/python3','-m','http.server','8765','--bind','127.0.0.1','--directory',str(webroot)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen(['firefox-esr','http://127.0.0.1:8765'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    firefox = wait_for(lambda: run('xdotool','search','--onlyvisible','--name','CyberLab Activity QA').splitlines()[0], timeout=40)
    run('xdotool','windowactivate','--sync',firefox)
    wait_for(lambda: request({'control':'status'})['state']['providers'].get('browser',{}).get('status')=='ready')
    type_text('WRONG_DRAFT'); key('ctrl+a'); type_text('FINAL_WEB_ANSWER'); key('Tab')
    type_text('NEVER_SAVE_PASSWORD'); key('Tab'); key('Return')
    submit = wait_for(lambda: find_event('web.submit','FINAL_WEB_ANSWER'))
    assert 'NEVER_SAVE_PASSWORD' not in json.dumps(events())
    assert 'WRONG_DRAFT' not in json.dumps(events())
    assert '[隐藏]' in json.dumps(submit, ensure_ascii=False)
    run('xdotool','mousemove','300','200','click','1')
    wait_for(lambda: find_event('ui.click','coordinates_only') or any(e['type']=='ui.click' for e in events()))
    result = {'session': session, 'passed': True, 'events': len(events()), 'state': request({'control':'status'})['state']}
    Path('/tmp/activity-qa-result.json').write_text(json.dumps(result, ensure_ascii=False))
    print(json.dumps(result, ensure_ascii=False))
    # Leave Firefox and the collector alive for resource sampling and soak QA.
    server.poll()


if __name__ == '__main__':
    main()
