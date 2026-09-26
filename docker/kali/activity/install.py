"""Install the local Firefox ESR extension and native bridge into the image."""
import json
from pathlib import Path
import zipfile

base = Path('/usr/local/lib/cyberlab-activity')
with zipfile.ZipFile(base / 'activity.xpi', 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in (base / 'firefox').glob('*'):
        archive.write(path, path.name)
host = Path('/usr/lib/mozilla/native-messaging-hosts')
host.mkdir(parents=True, exist_ok=True)
(host / 'cyberlab_activity.json').write_text(json.dumps({
    'name': 'cyberlab_activity', 'description': 'CyberLab local activity journal',
    'path': str(base / 'emit.py'), 'type': 'stdio', 'allowed_extensions': ['activity@cyberlab.local']}))
policies = Path('/usr/lib/firefox-esr/distribution')
policies.mkdir(parents=True, exist_ok=True)
(policies / 'policies.json').write_text(json.dumps({'policies': {
    'ExtensionSettings': {'activity@cyberlab.local': {'installation_mode': 'force_installed', 'install_url': 'file://' + str(base / 'activity.xpi')}},
    'Preferences': {'xpinstall.signatures.required': {'Value': False, 'Status': 'locked'},
                    'browser.aboutwelcome.enabled': {'Value': False, 'Status': 'locked'},
                    'browser.startup.homepage_override.mstone': {'Value': 'ignore', 'Status': 'locked'}},
    'Homepage': {'URL': 'about:blank', 'StartPage': 'homepage'},
    'OverrideFirstRunPage': '', 'OverridePostUpdatePage': '', 'DisableTelemetry': True,
    'DisableFirefoxStudies': True, 'DontCheckDefaultBrowser': True,
}}))
with Path('/etc/bash.bashrc').open('a') as stream:
    stream.write('\n. /usr/local/lib/cyberlab-activity/bash.sh\n')
with Path('/home/student/.bashrc').open('a') as stream:
    stream.write('\n. /usr/local/lib/cyberlab-activity/bash.sh\n')
