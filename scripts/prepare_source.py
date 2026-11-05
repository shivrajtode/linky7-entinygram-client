#!/usr/bin/env python3
"""Prepare EntinyGram sources for the Linky7 native (non-plugin) build."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

BLOCKED = {
    # Do not ship features that defeat recipient privacy/content protections.
    "entiny/privacy/ghost-mode.patch",
    "entiny/privacy/content-protection-bypass.patch",
    "entiny/privacy/save-self-destruct.patch",
    "entiny/media/save-stories.patch",
    "entiny/restrictions/gif-restriction-bypass.patch",
    "entiny/privacy/allow-screenshots.patch",
    "entiny/privacy/suppress-screenshot-notification.patch",
    "entiny/privacy/contact-changes.patch",
    "entiny/privacy/device-spoof.patch",
    "entiny/privacy/last-seen.patch",
    "entiny/media/one-time-peek.patch",
    "feature/show-deleted-replies.patch",
    "entiny/chat/reaction-read-sync.patch",
    "entiny/chat/instant-mark-reactions-read.patch",
    # This build uses only Linky7's independent OpenAI AI screens, not Gemini hooks.
    "entiny/ai/ai-compose.patch",
    "entiny/ai/chat-ai-deeplink.patch",
    "entiny/ai/ai-summary-inline.patch",
    "entiny/translator/translator.patch",
    "entiny/translator/input-translate.patch",
    # Avoid locally unlocking Telegram-paid/restricted limits.
    "entiny/premium/local-premium.patch",
    "entiny/restrictions/unlimited-fav-stickers.patch",
    "entiny/restrictions/unlimited-pinned-chats.patch",
    "entiny/restrictions/unlimited-folder-chats.patch",
    # Keep GPU-heavy blur/glass and unusually large image-cache additions off low-RAM devices.
    "entiny/ui/popup-swipeback-live-blur.patch",
    "entiny/ui/liquid-glass-controls.patch",
    "entiny/ui/liquid-glass-live-update.patch",
    "bugfix/image-cache-large-heap.patch",
}


BLOCK_TOKENS = (
    "ghost-mode", "ghost_mode", "stealth", "read-receipt", "read-suppression",
    "reaction-read", "hide-seen", "presence-spoof", "online-spoof", "typing-spoof",
    "device-spoof", "anti-deletion", "saved-deleted", "deleted-message", "deleted-messages",
    "edit-archive", "self-destruct", "view-once", "expiring-media", "save-stories",
    "story-download", "content-protection", "protected-forward", "forward-restriction",
    "screenshot-notification", "allow-screenshot", "screenshot-bypass", "skip-login",
    "login-countdown", "countdown-skip", "local-premium", "premium-unlock",
    "unlimited-pinned", "unlimited-fav", "unlimited-folder", "unlimited-stickers",
    "entiny/ai/", "translator", "input-translate", "liquid-glass",
    "popup-swipeback-live-blur", "image-cache-large-heap",
)


def adapt_playback_patch(repo: Path) -> None:
    """Remove only the translator-only context from the playback patch."""
    import re

    patch = (
        repo / "patches" / "bugfix" /
        "playback-progress-on-message-replace.patch"
    )

    if not patch.is_file():
        raise SystemExit("[ERROR] Playback patch is missing.")

    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)

    headers = [
        i for i, line in enumerate(lines)
        if line.startswith("@@ -")
    ]

    if len(headers) != 1:
        raise SystemExit("[ERROR] Unexpected playback patch structure.")

    h = headers[0]
    header = lines[h].rstrip("\r\n")

    match = re.match(
        r"^@@ -(\d+)(?:,(\d+))? "
        r"\+(\d+)(?:,(\d+))? @@(.*)$",
        header
    )

    if not match:
        raise SystemExit("[ERROR] Invalid playback patch header.")

    marker = "TranslateHelper.carryTranslation(old, messageObject);"

    matches = [
        i for i, line in enumerate(lines)
        if marker in line
    ]

    shift = 0

    if matches:
        if len(matches) != 1:
            raise SystemExit("[ERROR] Ambiguous translator context.")

        index = matches[0]

        # The translator line must be the first context line.
        if index != h + 1 or not lines[index].startswith(" "):
            raise SystemExit("[ERROR] Unexpected translator context position.")

        # The upstream patch has one empty context line between these statements.
        # In a unified diff, that blank context line is represented by a single space.
        anchor = index + 1
        if (
            anchor < len(lines)
            and lines[anchor].startswith(" ")
            and not lines[anchor].strip()
        ):
            anchor += 1

        if (
            anchor >= len(lines)
            or "addToPolls(messageObject, old);" not in lines[anchor]
        ):
            raise SystemExit("[ERROR] Playback patch anchor changed.")

        del lines[index]
        shift = 1

    elif (
        h + 1 < len(lines)
        and (
            "addToPolls(messageObject, old);" in lines[h + 1]
            or (
                h + 2 < len(lines)
                and lines[h + 1].startswith(" ")
                and not lines[h + 1].strip()
                and "addToPolls(messageObject, old);" in lines[h + 2]
            )
        )
    ):
        print("[OK] Playback patch already adapted.")
    else:
        raise SystemExit("[ERROR] Unknown playback patch state.")

    # Locate the complete hunk.
    end = next(
        (
            i for i in range(h + 1, len(lines))
            if lines[i].startswith("@@ -")
            or lines[i].startswith("diff --git ")
        ),
        len(lines)
    )

    body = lines[h + 1:end]

    # Preserve all seven playback additions.
    required = [
        "MediaController.getInstance().isPlayingMessage(messageObject)",
        "MessageObject player = MediaController.getInstance().getPlayingMessageObject();",
        "messageObject.audioProgress = player.audioProgress;",
        "messageObject.audioProgressSec = player.audioProgressSec;",
        "messageObject.audioPlayerDuration = player.audioPlayerDuration;",
        "messageObject.bufferedProgress = player.bufferedProgress;",
    ]

    for item in required:
        if not any(
            line.startswith("+") and item in line
            for line in body
        ):
            raise SystemExit(
                "[ERROR] Required playback code missing: " + item
            )

    # Recalculate both hunk lengths from the actual patch body.
    old_count = sum(
        line.startswith((" ", "-")) for line in body
    )
    new_count = sum(
        line.startswith((" ", "+")) for line in body
    )

    if old_count < 1 or new_count < old_count:
        raise SystemExit("[ERROR] Invalid recalculated hunk.")

    old_start = int(match.group(1)) + shift
    new_start = int(match.group(3)) + shift

    lines[h] = (
        f"@@ -{old_start},{old_count} "
        f"+{new_start},{new_count} @@{match.group(5)}\n"
    )

    result = "".join(lines)

    if marker in result:
        raise SystemExit("[ERROR] Translator dependency remains.")

    patch.write_text(result, encoding="utf-8")

    print("[OK] Translator-only context removed.")
    print(f"[OK] Hunk recalculated: {old_count} -> {new_count}.")
    print("[OK] All playback-progress additions preserved.")



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path, help="EntinyGram checkout directory")
    parser.add_argument("--builder", required=True, type=Path, help="Linky7 builder root")
    args = parser.parse_args()
    repo = args.repo.resolve()
    builder = args.builder.resolve()

    series = repo / "series"
    if not series.is_file():
        raise SystemExit(f"[ERROR] EntinyGram series file not found: {series}")
    lines = series.read_text(encoding="utf-8").splitlines()
    def is_blocked(line: str) -> bool:
        value = line.strip().lower().replace("\\", "/")
        if not value or value.startswith("#"):
            return False
        return value in BLOCKED or any(token in value for token in BLOCK_TOKENS)

    blocked_present = {line.strip() for line in lines if is_blocked(line)}
    kept = [line for line in lines if not is_blocked(line)]
    if len(kept) < 300:
        raise SystemExit(f"[ERROR] Unexpectedly short patch series after privacy filter ({len(kept)} entries); refusing to continue.")
    (repo / "series.linky7-original").write_text("\n".join(lines) + "\n", encoding="utf-8")
    series.write_text("\n".join(kept) + "\n", encoding="utf-8")
    adapt_playback_patch(repo)

    src = builder / "overlay" / "src" / "fork-app" / "linky7"
    if not src.is_dir() or not (src / "Linky7StudioActivity.kt").is_file():
        raise SystemExit("[ERROR] Native Linky7 Kotlin Activity is missing from builder overlay.")
    dest = repo / "src" / "fork-app" / "linky7"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "Linky7StudioActivity.kt", dest / "Linky7StudioActivity.kt")

    # Retain upstream files and all original source/license notices. This only edits the
    # active series file in the build checkout; the skipped patch files remain untouched.
    (repo / "LINKY7_BUILD_NOTES.md").write_text(
        "# Linky7 build notes\n\n"
        "This checkout builds a native Linky7 Studio Activity inside the EntinyGram Telegram Android client.\n"
        "The active patch series excludes privacy/content-protection bypasses, self-destruct/story saving,\n"
        "read-receipt/ghost-mode changes, login-countdown bypasses, local premium/restriction unlocks,\n"
        "EntinyGram Gemini AI/translator patches,\n"
        "and high-cost live blur/glass or large-image-cache patches intended to reduce GPU/RAM pressure on low-memory devices.\n"
        "All upstream patch files, original licences, and acknowledgements are retained in the checkout.\n",
        encoding="utf-8",
    )
    print(f"[OK] EntinyGram source prepared: {len(kept)} upstream patches kept; {len(blocked_present)} privacy/AI/restriction/performance patches excluded.")
    for entry in sorted(blocked_present):
        print(f"  [SKIP] {entry}")
    print("[OK] Native Linky7 Kotlin Activity placed into src/fork-app/linky7 (no plugin bridge).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
