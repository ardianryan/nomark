"""Point latest at the tested release manifest without rebuilding the image."""
import base64
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from release import check


def promote(suffix="", metadata_path="artifacts/image-metadata.json"):
    version = check()
    if os.environ.get('CI_COMMIT_TAG') != f'v{version}':
        raise RuntimeError('Image promotion requires a matching release tag')
    registry = os.environ['CI_REGISTRY']
    image = os.environ['CI_REGISTRY_IMAGE'] + suffix
    if not image.startswith(registry + '/'):
        raise RuntimeError('Image is outside the configured registry')
    repository = image[len(registry) + 1:]
    credentials = base64.b64encode(
        f'{os.environ["CI_REGISTRY_USER"]}:{os.environ["CI_REGISTRY_PASSWORD"]}'.encode()
    ).decode()
    query = urlencode({'service': 'container_registry', 'scope': f'repository:{repository}:pull,push'})
    request = Request(
        os.environ['CI_SERVER_URL'].rstrip('/') + '/jwt/auth?' + query,
        headers={'Authorization': f'Basic {credentials}'},
    )
    with urlopen(request, timeout=30) as response:
        token = json.load(response)['token']
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': ', '.join((
            'application/vnd.oci.image.index.v1+json',
            'application/vnd.oci.image.manifest.v1+json',
            'application/vnd.docker.distribution.manifest.list.v2+json',
            'application/vnd.docker.distribution.manifest.v2+json',
        )),
    }
    base = f'https://{registry}/v2/{repository}/manifests/'
    with urlopen(Request(base + version, headers=headers), timeout=30) as response:
        manifest = response.read()
        media_type = response.headers['Content-Type']
    digest = 'sha256:' + hashlib.sha256(manifest).hexdigest()
    metadata = json.loads(Path(metadata_path).read_text())
    if digest != metadata['containerimage.digest']:
        raise RuntimeError('Release manifest does not match the tested build')
    put_headers = {**headers, 'Content-Type': media_type}
    with urlopen(Request(base + 'latest', data=manifest, headers=put_headers, method='PUT'), timeout=30):
        pass
    with urlopen(Request(base + 'latest', headers=headers), timeout=30) as response:
        latest_digest = 'sha256:' + hashlib.sha256(response.read()).hexdigest()
    if latest_digest != digest:
        raise RuntimeError('Latest manifest digest did not match the release')
    print(f'{image}:latest = {image}:{version} ({digest})')


if __name__ == '__main__':
    from nmt_quality_gate import check_quality
    check_quality()
    promote()
    promote('/nmt', 'artifacts/nmt-image-metadata.json')
