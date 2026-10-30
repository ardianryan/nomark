"""Check release metadata, extract changelog notes, and publish a GitLab release."""
import json
import os
from pathlib import Path
import re
import sys
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def check():
    version = (ROOT / 'VERSION').read_text().strip()
    assert re.fullmatch(r'\d+\.\d+\.\d+(?:-alpha\.\d+)?', version), 'Invalid release version'
    python_version = re.sub(r'-alpha\.(\d+)$', r'a\1', version)
    assert tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version'] == python_version
    assert (ROOT / 'nomark/__init__.py').read_text().strip() == f'__version__ = "{version}"'
    package = json.loads((ROOT / 'package.json').read_text())
    lock = json.loads((ROOT / 'package-lock.json').read_text())
    assert package['version'] == lock['version'] == lock['packages']['']['version'] == version
    assert f'## [{version}] - ' in (ROOT / 'CHANGELOG.md').read_text(), 'Missing changelog'
    tag = os.environ.get('CI_COMMIT_TAG')
    assert not tag or tag == f'v{version}', 'Tag does not match VERSION'
    return version

def notes(version):
    section = (ROOT / 'CHANGELOG.md').read_text().split(f'## [{version}] - ', 1)[1]
    return section.split('\n', 1)[1].split('\n## ', 1)[0].strip() + '\n'

if __name__ == '__main__':
    version = check()
    command = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if command == 'check':
        print(version)
    elif command == 'notes':
        print(notes(version), end='')
    elif command == 'publish':
        project = os.environ['CI_PROJECT_URL']
        tag = f'v{version}'
        payload = {
            'name': f'NoMark {version}', 'tag_name': tag,
            'description': notes(version) + f'\n## Deployment image\n\n`{os.environ["CI_REGISTRY_IMAGE"]}:{version}`\n\nRolling image: `{os.environ["CI_REGISTRY_IMAGE"]}:latest` (currently follows alpha releases). It is promoted only after tests and container readiness checks succeed.\n\nPlatform: Linux amd64. The image contains the application and native PDF tools. VPS deployment is separate.\n',
            'assets': {'links': [
                {'name': 'Container registry', 'url': f'{project}/container_registry', 'link_type': 'package'},
                {'name': 'Deployment Compose file', 'url': f'{project}/-/raw/{tag}/deploy/compose.release.yaml', 'link_type': 'runbook'},
            ]},
        }
        request = urllib.request.Request(
            f'{os.environ["CI_API_V4_URL"]}/projects/{os.environ["CI_PROJECT_ID"]}/releases',
            data=json.dumps(payload).encode(),
            headers={'JOB-TOKEN': os.environ['CI_JOB_TOKEN'], 'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            print(json.load(response)['_links']['self'])
    else:
        raise SystemExit('Usage: release.py [check|notes|publish]')
