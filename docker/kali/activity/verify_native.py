"""Exercise a real GTK edit and Unicode clipboard paste in disposable QA only."""
import json
import os
from pathlib import Path
import subprocess
import time
from verify_desktop import run, key, type_text, wait_for, events, find_event


def main():
    os.environ.update(json.loads(Path('/tmp/runtime-student/desktop-env.json').read_text()))
    fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('native_fixture.py'))])
    try:
        window = wait_for(lambda: run('xdotool','search','--onlyvisible','--name','^CyberLab Native QA$').splitlines()[0])
        run('xdotool','windowactivate','--sync',window)
        time.sleep(.4)
        type_text('DRAFT_NOT_SAVED');key('ctrl+a');key('ctrl+v');key('Tab')
        wait_for(lambda: find_event('ui.change','中文粘贴_FINAL'))
        assert 'DRAFT_NOT_SAVED' not in json.dumps(events())
        import gi
        gi.require_version('Atspi', '2.0')
        from gi.repository import Atspi
        Atspi.init()
        desktop = Atspi.get_desktop(0)
        stack = [desktop.get_child_at_index(i) for i in range(desktop.get_child_count()) if desktop.get_child_at_index(i).get_process_id() == fixture.pid]
        button = None
        while stack:
            item = stack.pop()
            if item.get_name() == '保存答案':
                button = item.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                break
            stack.extend(item.get_child_at_index(i) for i in range(item.get_child_count()))
        assert button is not None
        run('xdotool','mousemove',str(button.x + button.width // 2),str(button.y + button.height // 2),'click','1')
        wait_for(lambda: find_event('ui.click','保存答案'))
        print(json.dumps({'native_edit':True,'unicode_clipboard':True,'named_click':True}, ensure_ascii=False))
    finally:
        fixture.terminate();fixture.wait(timeout=5)


if __name__ == '__main__':
    main()
