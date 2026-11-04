#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_NAME="${LINKY7_REPO_NAME:-linky7-entinygram-client}"

fail() { printf '\n[ERROR] %s\n' "$*" >&2; exit 1; }
info() { printf '\n\033[1;36m[LINKY7]\033[0m %s\n' "$*"; }

if ! command -v pkg >/dev/null 2>&1; then
  fail "Run this builder in Termux, not in Android's normal shell."
fi

# Install only the lightweight Termux-side tools. APK compilation is performed by
# GitHub Actions because Google's NDK downloads provide Linux x86-64 host tooling,
# whereas this tablet is Android ARM64. Root cannot change that host ABI mismatch.
missing=()
for tool in gh git jq python; do command -v "$tool" >/dev/null 2>&1 || missing+=("$tool"); done
if ((${#missing[@]})); then
  info "Installing Termux tools: ${missing[*]}"
  pkg update -y
  pkg install -y gh git jq python
fi

if ! gh auth status >/dev/null 2>&1; then
  cat <<'EOF'
[SETUP] GitHub CLI is not authenticated.
Run:
  gh auth login -h github.com -p https -s repo,workflow -w
Then run this build.sh again. The token needs repo + workflow scopes so this script can create the source repo, save build secrets and dispatch Actions.
EOF
  exit 2
fi

OWNER="$(gh api user --jq .login 2>/dev/null)" || fail "Cannot identify the active GitHub account. Check gh auth status."
[[ -n "$OWNER" ]] || fail "GitHub CLI returned an empty username."
REPO="$OWNER/$REPO_NAME"
info "Active GitHub account: $OWNER"
info "Build repository: $REPO (public, source + GPL notices retained)"

if [[ -z "${LINKY7_TG_API_ID:-}" ]]; then
  printf '\nTelegram API ID (from https://my.telegram.org/apps): '
  read -r LINKY7_TG_API_ID
fi
if [[ -z "${LINKY7_TG_API_HASH:-}" ]]; then
  printf 'Telegram API HASH (input hidden): '
  IFS= read -r -s LINKY7_TG_API_HASH
  printf '\n'
fi
[[ "$LINKY7_TG_API_ID" =~ ^[1-9][0-9]{5,11}$ ]] || fail "Telegram API ID must be numeric (6-12 digits)."
[[ "$LINKY7_TG_API_HASH" =~ ^[0-9a-fA-F]{32}$ ]] || fail "Telegram API HASH must contain exactly 32 hexadecimal characters."

# Use a unique temporary checkout. It does not touch Android SDK/Gradle caches or
# delete any files outside this temporary builder workspace.
WORK="$(mktemp -d "${TMPDIR:-$HOME}/linky7-cloud-build.XXXXXX")"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

if gh repo view "$REPO" >/dev/null 2>&1; then
  info "Updating the existing Linky7 build repository..."
  gh repo clone "$REPO" "$WORK/repo" >/dev/null || fail "Could not clone $REPO. Check repository permissions."
  DEST="$WORK/repo"
  cp -a "$ROOT/.github" "$DEST/"
  cp -a "$ROOT/scripts" "$DEST/"
  cp -a "$ROOT/overlay" "$DEST/"
  cp -a "$ROOT/README.md" "$ROOT/THIRD_PARTY_NOTICES.md" "$ROOT/LICENSE" "$ROOT/.gitignore" "$DEST/"
  cp -a "$ROOT/BUILD-VERSION" "$DEST/"
  cp -a "$ROOT/build.sh" "$DEST/"
  cd "$DEST"
  git config core.autocrlf false
  git add -A
  if ! git diff --cached --quiet; then
    git config user.name "Linky7 Builder"
    EMAIL="$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"')"
    git config user.email "$EMAIL"
    git commit -m "Update Linky7 native EntinyGram build sources"
    git push origin HEAD:main
  fi
else
  info "Creating public source/build repository..."
  mkdir -p "$WORK/repo"
  DEST="$WORK/repo"
  cp -a "$ROOT/.github" "$ROOT/scripts" "$ROOT/overlay" "$DEST/"
  cp -a "$ROOT/README.md" "$ROOT/THIRD_PARTY_NOTICES.md" "$ROOT/LICENSE" "$ROOT/.gitignore" "$DEST/"
  cp -a "$ROOT/BUILD-VERSION" "$DEST/"
  cp -a "$ROOT/build.sh" "$DEST/"
  cd "$DEST"
  git init -b main >/dev/null
  git config core.autocrlf false
  git config user.name "Linky7 Builder"
  EMAIL="$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"')"
  git config user.email "$EMAIL"
  git add -A
  git commit -m "Initial Linky7 native EntinyGram builder" >/dev/null
  gh repo create "$REPO" --public --source "$DEST" --remote origin --push >/dev/null || fail "Could not create/push $REPO. Check the repository name or permissions."
fi

# Set GitHub Actions secrets through stdin so neither API value is written to shell history.
printf '%s' "$LINKY7_TG_API_ID" | gh secret set LINKY7_TG_API_ID --repo "$REPO" || fail "Could not set LINKY7_TG_API_ID secret."
printf '%s' "$LINKY7_TG_API_HASH" | gh secret set LINKY7_TG_API_HASH --repo "$REPO" || fail "Could not set LINKY7_TG_API_HASH secret."
unset LINKY7_TG_API_ID LINKY7_TG_API_HASH

info "Triggering the native Telegram client build..."
BEFORE="$(gh run list --repo "$REPO" --workflow build-linky7.yml --limit 1 --json databaseId --jq '.[0].databaseId // ""' 2>/dev/null || true)"
gh workflow run build-linky7.yml --repo "$REPO" --ref main >/dev/null || fail "Could not dispatch GitHub Actions. Enable Actions for this repository, then retry."

RUN_ID=""
for _ in $(seq 1 36); do
  CURRENT="$(gh run list --repo "$REPO" --workflow build-linky7.yml --branch main --limit 1 --json databaseId --jq '.[0].databaseId // ""' 2>/dev/null || true)"
  if [[ -n "$CURRENT" && "$CURRENT" != "$BEFORE" ]]; then RUN_ID="$CURRENT"; break; fi
  sleep 5
done
[[ -n "$RUN_ID" ]] || fail "Workflow was dispatched but its run ID was not found. View: https://github.com/$REPO/actions"
info "GitHub Actions run: https://github.com/$REPO/actions/runs/$RUN_ID"

if ! gh run watch "$RUN_ID" --repo "$REPO" --exit-status; then
  echo
  gh run view "$RUN_ID" --repo "$REPO" --json url,conclusion --jq '"Build conclusion: \(.conclusion)\nRun: \(.url)"' 2>/dev/null || true
  fail "Cloud build failed. Open the run URL above and share the final error section; do not upload API secrets."
fi

DOWNLOAD_DIR="$HOME/storage/downloads"
mkdir -p "$DOWNLOAD_DIR"
ARTIFACT_DIR="$DOWNLOAD_DIR/Linky7-APK-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ARTIFACT_DIR"
gh run download "$RUN_ID" --repo "$REPO" --name Linky7-client-apk --dir "$ARTIFACT_DIR" || fail "Build succeeded but APK artifact download failed."
[[ -s "$ARTIFACT_DIR/Linky7.apk" ]] || fail "Artifact did not contain Linky7.apk. Inspect: $ARTIFACT_DIR"
cp -f "$ARTIFACT_DIR/Linky7.apk" "$DOWNLOAD_DIR/Linky7.apk"

printf '\n\033[1;32m[OK] Linky7 APK built successfully.\033[0m\n'
printf 'APK: %s\n' "$DOWNLOAD_DIR/Linky7.apk"
printf 'Artifact: %s\n' "$ARTIFACT_DIR"
printf 'Source: https://github.com/%s\n' "$REPO"
printf '\nInstall Linky7.apk from Downloads. If a previous EntinyGram build with a different signature is installed, uninstall that build first.\n'
