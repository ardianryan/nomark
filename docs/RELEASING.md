# Releasing NoMark

## Version policy

`VERSION` is the public SemVer version. `nomark/__init__.py`, `package.json`, and the root entries in `package-lock.json` must match it. Python metadata uses the equivalent PEP 440 spelling: `0.1.0-alpha.1` becomes `0.1.0a1`. The application reports its version through `/health`; the public interface has no release badge.

Every change must be described in `CHANGELOG.md` before release. While preparing a release, changes use its version. After publishing a tag, increment the version for subsequent changes; never overwrite a release tag or versioned image. Update `deploy/compose.release.yaml` for each release. Run `python scripts/release.py check` before committing. Rebuild the browser bundle after changing the Python package version.

## Pipeline

GitLab CI runs the Python and browser tests. The default branch also builds an amd64 application image with rootless BuildKit and starts it for a readiness check. Its image tag is `sha-<full commit SHA>`.

Once the default branch pipeline is green:

```sh
python3 scripts/release.py check
git tag -a v0.1.0-alpha.1 -m 'NoMark 0.1.0-alpha.1'
git push origin v0.1.0-alpha.1
```

The tag pipeline checks the version again, tests, builds the versioned image, checks readiness, and publishes a GitLab release from the changelog. An alpha receives no `latest` tag. Registry publishing uses the ephemeral GitLab job credentials; no personal access token is committed. The runner must support rootless BuildKit and have registry access. Build metadata containing the image digest is retained as a pipeline artifact for one year.

## Deployment

The published image is `registry.gitlab.com/ardianryan/nomark:0.1.0-alpha.1`. It includes FastAPI, local frontend assets, the pinned cleaners, ExifTool, qpdf, and Ghostscript in one container. Caddy remains on the host. No VPS deployment happens in the release pipeline.

```sh
docker compose -f deploy/compose.release.yaml pull
docker compose -f deploy/compose.release.yaml up -d
curl --fail http://127.0.0.1:8000/health
```

Review [deployment](DEPLOYMENT.md) and the changelog's alpha limitations first. The initial build targets Linux amd64. For an immutable deployment, replace the tag in a private Compose copy with the registry digest shown in the build metadata, then retain that digest for rollback. Check that the registry image exists and the tag pipeline succeeded before deploying. A source audit alone does not establish that hostile document processing or production infrastructure is secure.

## README artwork

`docs/assets/banner.svg` adapts to system color preference; the light and dark variants support Markdown picture elements. Sources use absolute raw GitLab URLs because GitLab does not rewrite relative `srcset` URLs. GitHub supports the same picture markup. All lettering is outlined, with the original wordmark retained. Regenerate with `python scripts/readme_banner.py /path/to/Avenir\ Next.ttc` and development-only `fonttools`. No font binary is distributed.
