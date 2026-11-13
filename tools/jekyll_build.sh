#!/bin/sh
# Builds the site with the image the GitHub Pages workflow uses (actions/jekyll-build-pages), without deploying, then
# checks the built site with html-proofer (pinned below): internal links, the translation pills and hreflang links,
# images and scripts. Needs Docker and network access (remote theme, Debian and RubyGems packages). The source is
# mounted read-only and the output stays in the container.
set -eu
# Without a running Docker daemon (Colima stopped) the local build is skipped, not failed: the stock GitHub Pages
# workflow builds the same image on every push, and no Ruby/Jekyll toolchain is kept on the host to duplicate it.
if ! docker info >/dev/null 2>&1; then
  echo "jekyll_build.sh: skipped: no Docker daemon (colima start); the GitHub Pages workflow builds on push" >&2
  exit 0
fi
root=$(cd "$(dirname "$0")/.." && pwd)
# The image tag follows the workflow's SHA pin through its version comment; a bump edits both (ai/upstreams.json).
tag=$(sed -n 's/.*uses: actions\/jekyll-build-pages@[0-9a-f]\{40\} # \(v[0-9][0-9.]*\)$/\1/p' "$root/.github/workflows/jekyll-gh-pages.yml")
case $tag in v[0-9]*.[0-9]*) ;; *) echo "jekyll_build.sh: no 'jekyll-build-pages@<sha> # vX.Y.Z' pin in the workflow" >&2; exit 1 ;; esac
# html-proofer, registered in ai/upstreams.json; it loads libcurl, which the image lacks.
proofer=5.2.3
# A source the Docker daemon cannot see mounts empty and would build an empty site: fail on it instead.
# Site URLs carry `url` and `baseurl` from _config.yml; html-proofer maps them back to paths in the built folder.
exec docker run --rm --platform linux/amd64 -v "$root":/src:ro \
  -e JEKYLL_ENV=production -e PAGES_REPO_NWO=ntinco/abap-articles -e PROOFER="$proofer" \
  --entrypoint /bin/sh "ghcr.io/actions/jekyll-build-pages:$tag" -c '
set -eu
test -f /src/_config.yml
/usr/local/bundle/bin/github-pages build --source /src --destination /tmp/_site
# A build silently lets one file overwrite another at the same destination (a redirect_from page over an article);
# the Jekyll doctor reports such conflicts and fails on them.
/usr/local/bundle/bin/jekyll doctor --source /src --destination /tmp/_site
test -f /tmp/_site/index.html
(apt-get update -qq && apt-get install -y -qq --no-install-recommends libcurl4) >/dev/null
gem install html-proofer -v "$PROOFER" --no-document --quiet
# --swap-urls takes `regex:replacement` pairs, a colon inside a regex escaped as `\:`.
swap=$(ruby -ryaml -e "c = YAML.load_file(%q(/src/_config.yml)); u, b = c[%q(url)].to_s, c[%q(baseurl)].to_s
  puts [u + b, b].reject(&:empty?).map { |s| %q(^) + Regexp.escape(s).gsub(%q(:), %q(\\:)) + %q(:) }.join(%q(,))")
exec htmlproofer /tmp/_site --disable-external --swap-urls "$swap"'
