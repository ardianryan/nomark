# Releasing NoMark

## Version policy

`VERSION` is the public SemVer version. `nomark/__init__.py`, `package.json`, and the root entries in `package-lock.json` must match it. Python metadata uses the equivalent PEP 440 spelling: `0.1.0-alpha.6` becomes `0.1.0a6`. The application reports its version through `/health`; the public interface has no release badge.

Every change must be described in `CHANGELOG.md` before release. While preparing a release, changes use its version. After publishing a tag, increment the version for subsequent changes; never overwrite a release tag or versioned image. Update `deploy/compose.release.yaml` for each release. Run `python scripts/release.py check` before committing. Rebuild the browser bundle after changing the Python package version.

## Pipeline

GitLab CI runs the Python and browser tests. The default branch also builds an amd64 application image with rootless BuildKit and starts it for a readiness check. Its image tag is `sha-<full commit SHA>`.

Once the default branch pipeline is green:

```sh
python3 scripts/release.py check
git tag -a v0.1.0-alpha.6 -m 'NoMark 0.1.0-alpha.6'
git push origin v0.1.0-alpha.6
```

The tag pipeline checks the version again, tests, builds the versioned image, checks readiness, and publishes a GitLab release from the changelog. After the readiness check succeeds, a serialized promotion job copies the release manifest to `latest` and verifies that both digests match the build artifact. `latest` intentionally follows alpha releases until stable releases are available. It is not updated by branch builds. Publish releases in version order; rerunning an older tag pipeline can move `latest` back. Registry publishing uses the ephemeral GitLab job credentials; no personal access token is committed. The runner must support rootless BuildKit and have registry access. Build metadata containing the image digest is retained as a pipeline artifact for one year.

## Deployment

The release configuration targets `registry.gitlab.com/ardianryan/nomark:0.1.0-alpha.6`; a candidate is not published until its tag pipeline succeeds. The image includes FastAPI, local frontend assets, the pinned cleaners, ExifTool, qpdf, and Ghostscript in one container. The optional NMT override uses `/nmt` with the same version. The complete `deploy/compose.portainer.yaml` stack uses both rolling `latest` images and retains the existing Portainer volume/network names. The root development Compose builds both services. Caddy remains on the host. No VPS deployment happens in the release pipeline.

```sh
docker compose -f deploy/compose.release.yaml pull
docker compose -f deploy/compose.release.yaml up -d
curl --fail http://127.0.0.1:8000/health
```

Review [deployment](DEPLOYMENT.md) and the changelog's alpha limitations first. The initial build targets Linux amd64. For an immutable deployment, replace the tag in a private Compose copy with the registry digest shown in the build metadata, then retain that digest for rollback. Check that the registry image exists and the tag pipeline succeeded before deploying. A source audit alone does not establish that hostile document processing or production infrastructure is secure.

## README artwork

`docs/assets/banner.svg` adapts to system color preference; the light and dark variants support Markdown picture elements. Sources use absolute raw GitLab URLs because GitLab does not rewrite relative `srcset` URLs. GitHub supports the same picture markup. All lettering is outlined, with the original wordmark retained. Regenerate with `python scripts/readme_banner.py /path/to/Avenir\ Next.ttc` and development-only `fonttools`. No font binary is distributed.

## Portainer rolling updates

Use `image: registry.gitlab.com/ardianryan/nomark:latest` in the Portainer stack to avoid editing the version for every release. Pull and redeploy the stack after a new release; merely publishing an image does not update a running container. History and preferences remain in the browser. Allow active processing to finish before redeploying. For rollback, replace `latest` with a previous version tag and redeploy. The versioned Compose example continues to pin a release for reproducible deployments.

## Optional NMT release gate

Both main and `/nmt` images are built and smoke-tested by GitLab. Tagged builds and latest promotion additionally require the original forty-sample quality evaluation and the current forty-sample holdout in `docs/nmt-holdout.json`. Most inputs are preserved, so passing this gate is not evidence of broad rewriting quality. Source changes invalidate the reports. SHA images may be used for isolated staging. Pushes to `main` do not publish releases or move `latest`: after the branch pipeline succeeds, push the matching annotated version tag, wait for its complete pipeline, and verify both latest/version digests. Mirror the tag and create a GitHub prerelease with the same changelog notes; no GitHub Actions are needed. See [Paraphrasing](PARAPHRASE.md).
