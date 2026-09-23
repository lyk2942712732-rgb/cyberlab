"""Smoke-test built images on a Linux Docker host, without starting Kali desktops."""
import json
import time
import uuid
from pathlib import Path
import docker

PROBE = r'''
import base64, html, json, sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener
slug, flag = sys.argv[1:]
browser = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
def get(path, form=None):
    try:
        response = browser.open('http://127.0.0.1:8000' + path, None if form is None else urlencode(form).encode(), timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, html.unescape(response.read().decode())
assert get('/health') == (200, 'ok')
assert flag not in get('/')[1]
if slug == 'access':
    assert flag not in get('/orders?id=1001')[1]
    assert flag in get('/orders?id=1002')[1]
elif slug == 'config':
    assert '/backup/config.json' in get('/robots.txt')[1]
    assert flag in get('/backup/config.json')[1]
elif slug == 'supply':
    assert flag not in get('/install', {'source': 'official', 'package': 'lesson-theme'})[1]
    assert flag in get('/install', {'source': 'community', 'package': 'lesson-theme'})[1]
elif slug == 'crypto':
    assert base64.b64decode(json.loads(get('/backup')[1])['encrypted_secret']).decode() == flag
elif slug == 'sqli':
    assert get('/login', {'username': 'admin', 'password': 'wrong'})[0] == 403
    assert flag in get('/login', {'username': "admin' -- ", 'password': 'wrong'})[1]
elif slug == 'design':
    assert flag not in get('/buy', {})[1]
    get('/redeem', {'coupon': 'WELCOME'})
    assert flag not in get('/buy', {})[1]
    get('/redeem', {'coupon': 'WELCOME'})
    assert flag in get('/buy', {})[1]
elif slug == 'auth':
    assert flag not in get('/reset-password', {'username': 'student'})[1]
    assert flag in get('/reset-password', {'username': 'admin'})[1]
elif slug == 'integrity':
    assert flag not in get('/profile', {'token': get('/token')[1]})[1]
    token = base64.b64encode(b'{"role":"admin"}').decode()
    assert flag in get('/profile', {'token': token})[1]
elif slug == 'logging':
    for pin in ('00', '01', '02'):
        assert get('/pin', {'pin': pin})[0] == 403
    assert json.loads(get('/audit')[1])['alerts'] == []
    assert flag in get('/pin', {'pin': '03'})[1]
elif slug == 'exception':
    assert get('/vault', {'policy_version': '1'})[0] == 403
    assert flag in get('/vault', {'policy_version': 'invalid'})[1]
elif slug == 'xss':
    payload = '<script>document.title="xss"</script>'
    assert payload in get('/search?' + urlencode({'q': payload}))[1]
elif slug == 'ssrf':
    assert get('/preview?' + urlencode({'url': 'http://example.com'}))[0] == 400
    assert flag in get('/preview?' + urlencode({'url': 'http://127.0.0.1:9000/admin'}))[1]
print('PASS', slug)
'''


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "dist/web-security/manifest.json").read_text())
    client = docker.from_env(timeout=30)
    resources = []
    try:
        for item in manifest:
            identifier = uuid.uuid4().hex
            network = client.networks.create("web-check-" + identifier, internal=True, labels={"cyberlab.validation": identifier})
            resources.append((network, None, item, None))
            flag = "flag{" + identifier + "}"
            container = client.containers.run(item["image_id"], detach=True, network=network.id,
                                              labels={"cyberlab.validation": identifier}, environment={"LAB_FLAG": flag},
                                              nano_cpus=500_000_000, mem_limit="128m", memswap_limit="128m", pids_limit=256,
                                              cap_drop=["ALL"], security_opt=["no-new-privileges:true"])
            resources[-1] = network, container, item, flag
        deadline = time.monotonic() + 90
        for _, container, item, flag in resources:
            while time.monotonic() < deadline:
                container.reload()
                assert container.status == "running", item["slug"] + " exited"
                if container.attrs["State"].get("Health", {}).get("Status") == "healthy":
                    break
                time.sleep(1)
            else:
                raise TimeoutError(item["slug"] + " healthcheck")
            assert not container.attrs["HostConfig"]["PortBindings"]
            result = container.exec_run(["python", "-c", PROBE, item["slug"], flag])
            if result.exit_code:
                raise RuntimeError(item["slug"] + ": " + result.output.decode())
            print(result.output.decode().strip(), flush=True)
    finally:
        for network, container, _, _ in reversed(resources):
            try:
                if container:
                    container.remove(force=True, v=True)
            finally:
                network.remove()
        client.close()


if __name__ == "__main__":
    main()
