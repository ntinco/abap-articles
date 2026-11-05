#!/bin/sh
# Builds the site with the image the GitHub Pages workflow uses (actions/jekyll-build-pages), without deploying.
# Needs Docker and network access (remote theme). The source is mounted read-only and the output stays in the container.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
# The image tag follows the workflow's SHA pin through its version comment, which Dependabot rewrites on each bump.
tag=$(sed -n 's/.*uses: actions\/jekyll-build-pages@[0-9a-f]\{40\} # \(v[0-9][0-9.]*\)$/\1/p' "$root/.github/workflows/jekyll-gh-pages.yml")
case $tag in v[0-9]*.[0-9]*) ;; *) echo "jekyll_build.sh: no 'jekyll-build-pages@<sha> # vX.Y.Z' pin in the workflow" >&2; exit 1 ;; esac
# A source the Docker daemon cannot see mounts empty and would build an empty site: fail on it instead.
exec docker run --rm --platform linux/amd64 -v "$root":/src:ro \
  -e JEKYLL_ENV=production -e PAGES_REPO_NWO=ntinco/abap-craft \
  --entrypoint /bin/sh "ghcr.io/actions/jekyll-build-pages:$tag" \
  -c 'test -f /src/_config.yml && exec /usr/local/bundle/bin/github-pages build --source /src --destination /tmp/_site'
