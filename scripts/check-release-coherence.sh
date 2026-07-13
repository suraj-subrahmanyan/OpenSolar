#!/usr/bin/env bash
# Release-coherence gate: the version/channel/mode/reference invariants that
# let a cut tag actually install, update, and verify itself.
#
# Born from the 2026-07-08 system-test bench (P6 corpus PKG-001..004): rc.8
# shipped a get-solar.sh channel default still on rc.6, so `solar update`
# DOWNGRADED fresh rc.8 installs; the pipx package carried three different
# versions and pointed at the wrong repo; three verification scripts were
# 644; and a smoke referenced a script that did not exist. Every check here
# makes one of those classes structurally impossible to ship again.
#
# Run standalone from the repo root, or via release-cut.sh (which runs it
# inside the scratch orphan tree before a cut).
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
FAIL=0

log() { printf '%s\n' "$*"; }
fail() { log "FAIL: $*"; FAIL=1; }
ok() { log "ok: $*"; }

VERSION="$(tr -d '[:space:]' < VERSION 2>/dev/null || true)"
if [ -z "$VERSION" ]; then
    fail "VERSION file missing or empty"
    echo "release-coherence: FAIL"; exit 1
fi
TAG="v$VERSION"
# PEP 440 form for the pipx package: 1.0.0-rc.8 -> 1.0.0rc8
PEP440="$(printf '%s' "$VERSION" | sed 's/-rc\./rc/')"

# ---- check 1: get-solar.sh channel default == the version being cut -------
log "check 1: get-solar.sh SOLAR_CHANNEL default == $TAG (PKG-001)"
CHANNEL_DEFAULT="$(sed -n 's/^SOLAR_CHANNEL="\${SOLAR_CHANNEL:-\([^}]*\)}"$/\1/p' get-solar.sh)"
if [ -z "$CHANNEL_DEFAULT" ]; then
    fail "could not parse SOLAR_CHANNEL default from get-solar.sh"
elif [ "$CHANNEL_DEFAULT" != "$TAG" ]; then
    fail "get-solar.sh channel default is '$CHANNEL_DEFAULT', VERSION is '$VERSION' (installs will record the wrong update channel)"
else
    ok "channel default $CHANNEL_DEFAULT"
fi

# ---- check 2: pipx package version + URL coherence (PKG-003) --------------
log "check 2: pipx distribution coherent with VERSION"
PIPX=distribution/pipx
PYPROJECT_V="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$PIPX/pyproject.toml")"
INIT_V="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$PIPX/opensolar_cli/__init__.py")"
[ "$PYPROJECT_V" = "$PEP440" ] && ok "pyproject version $PYPROJECT_V" \
    || fail "pipx pyproject version '$PYPROJECT_V' != '$PEP440'"
[ "$INIT_V" = "$PEP440" ] && ok "__init__ version $INIT_V" \
    || fail "pipx __init__ version '$INIT_V' != '$PEP440'"
if grep -q "raw.githubusercontent.com/suraj-subrahmanyan/OpenSolar/$TAG/" "$PIPX/opensolar_cli/cli.py"; then
    ok "PUBLIC_GET_SOLAR_URL pinned to the maintained repo at $TAG"
else
    fail "pipx cli.py PUBLIC_GET_SOLAR_URL is not the maintained repo at $TAG"
fi
STALE_TAGS="$(grep -rhoIE --exclude-dir=__pycache__ 'v1\.0\.0-rc\.[0-9]+' "$PIPX" | grep -v "^$TAG$" | sort -u || true)"
if [ -n "$STALE_TAGS" ]; then
    fail "pipx tree references stale tags: $(printf '%s' "$STALE_TAGS" | tr '\n' ' ')"
else
    ok "no stale tag references in $PIPX"
fi

# ---- check 3: every shebang script in scripts/ is executable (PKG-002) ----
log "check 3: scripts/*.sh with shebangs are 755 in the index"
BAD_MODE=0
while IFS= read -r line; do
    mode="${line%% *}"
    path="${line##*	}"
    case "$(head -c2 "$path" 2>/dev/null)" in
        '#!')
            if [ "$mode" != "100755" ]; then
                fail "$path has a shebang but index mode $mode"
                BAD_MODE=1
            fi
            ;;
    esac
done < <(git ls-files -s -- 'scripts/*.sh')
[ "$BAD_MODE" -eq 0 ] && ok "all shebang scripts executable"

# ---- check 4: intra-repo script references exist (PKG-004) ----------------
log "check 4: scripts/ referenced paths exist"
BAD_REF=0
while IFS= read -r ref; do
    if [ ! -e "$ref" ]; then
        fail "referenced path does not exist: $ref"
        BAD_REF=1
    fi
done < <(grep -rhoE '"?scripts/[A-Za-z0-9._-]+\.(sh|ts|py)"?' scripts/ \
    | tr -d '"' | sort -u)
[ "$BAD_REF" -eq 0 ] && ok "all script references resolve"

# ---- check 5: solar update refuses version downgrades (PKG-001b) ----------
log "check 5: bin/solar version-compare guard behaves"
probe() {
    got="$(bash bin/solar version-compare "$1" "$2" 2>/dev/null)"
    if [ "$got" != "$3" ]; then
        fail "version-compare $1 $2 -> '$got' (want '$3')"
    fi
}
if grep -q "version-compare" bin/solar; then
    probe 1.0.0-rc.6 1.0.0-rc.8 lt
    probe 1.0.0-rc.8 1.0.0-rc.6 gt
    probe 1.0.0-rc.8 1.0.0-rc.8 eq
    probe 1.0.0-rc.8 1.0.0 lt      # rc precedes its GA release
    probe 1.0.0 1.0.0-rc.8 gt
    probe unknown 1.0.0-rc.8 unknown
    [ "$FAIL" -eq 0 ] && ok "version-compare guard present and correct"
else
    fail "bin/solar has no version-compare guard (updates cannot refuse downgrades)"
fi

# ---- check 6: receipt.sh channel fallback derives from VERSION ------------
# PKG-001 sibling found by real-machine install verification (2026-07-13): a
# direct install.sh run (dev tree, desktop-bundled Resources/harness) recorded
# channel v1.0.0-rc.6 from a hardcoded fallback in receipt.sh, so the very
# first `solar update` hit the downgrade guard. The fallback must be derived
# from the VERSION file, never a literal tag that goes stale at the next cut.
log "check 6: receipt.sh channel fallback derives from VERSION (PKG-001 sibling)"
RECEIPT=lib/installer/receipt.sh
if grep -Eq 'SOLAR_CHANNEL"\) or "v[0-9]' "$RECEIPT"; then
    fail "receipt.sh hardcodes a channel fallback tag (grep: 'or \"v<digit>'); derive it from VERSION instead"
elif ! grep -q 'channel_fallback' "$RECEIPT"; then
    fail "receipt.sh has no channel_fallback derivation (channel fallback must come from the VERSION file)"
else
    ok "receipt channel fallback is VERSION-derived"
fi

if [ "$FAIL" -eq 0 ]; then
    log "release-coherence: PASS"
    exit 0
fi
log "release-coherence: FAIL"
exit 1
