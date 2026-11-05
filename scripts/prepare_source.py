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




def adapt_premium_badge_patch(repo: Path) -> None:
    """Drop the excluded local-premium-only context from the badge display patch."""
    import re

    patch = repo / "patches" / "entiny" / "premium" / "premium-badge-dialogs.patch"
    if not patch.is_file():
        raise SystemExit("[ERROR] Premium badge patch is missing.")

    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)
    marker = "desu.inugram.helpers.LocalPremiumHelper.applyToSelfUser(user, currentAccount);"
    user_badge = "desu.inugram.helpers.badges.BadgeRegistry.applyTo(user);"
    chat_badge = "desu.inugram.helpers.badges.BadgeRegistry.applyTo(chat);"
    matches = [i for i, line in enumerate(lines) if marker in line]

    if matches:
        if len(matches) != 1:
            raise SystemExit("[ERROR] Ambiguous LocalPremiumHelper context in premium badge patch.")
        index = matches[0]
        if not lines[index].startswith(" "):
            raise SystemExit("[ERROR] LocalPremiumHelper line is not patch context; refusing to alter a code change.")
        if sum(line.startswith("+") and user_badge in line for line in lines) != 1:
            raise SystemExit("[ERROR] Expected exactly one user BadgeRegistry addition.")
        if sum(line.startswith("+") and chat_badge in line for line in lines) != 1:
            raise SystemExit("[ERROR] Expected exactly one chat BadgeRegistry addition.")

        hunk_start = max((i for i in range(index) if lines[i].startswith("@@ -")), default=-1)
        if hunk_start < 0:
            raise SystemExit("[ERROR] Could not locate premium badge hunk header.")
        header = lines[hunk_start].rstrip("\r\n")
        match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$", header)
        if not match:
            raise SystemExit("[ERROR] Invalid premium badge hunk header.")

        del lines[index]
        hunk_end = next(
            (i for i in range(hunk_start + 1, len(lines))
             if lines[i].startswith("@@ -") or lines[i].startswith("diff --git ")),
            len(lines),
        )
        body = lines[hunk_start + 1:hunk_end]
        old_count = sum(line.startswith((" ", "-")) for line in body)
        new_count = sum(line.startswith((" ", "+")) for line in body)
        if old_count < 1 or new_count < old_count:
            raise SystemExit("[ERROR] Invalid premium badge hunk after context removal.")
        lines[hunk_start] = (
            f"@@ -{match.group(1)},{old_count} +{match.group(3)},{new_count} @@{match.group(5)}\n"
        )
        result = "".join(lines)
        if marker in result:
            raise SystemExit("[ERROR] LocalPremiumHelper dependency remains in premium badge patch.")
        if result.count(user_badge) != 1 or result.count(chat_badge) != 1:
            raise SystemExit("[ERROR] Premium badge changes were not preserved exactly.")
        patch.write_text(result, encoding="utf-8")
        print(f"[OK] Premium badge patch adapted; first hunk recalculated {old_count}/{new_count}.")
        print("[OK] Both BadgeRegistry additions preserved; local-premium remains excluded.")
        return

    # Safe repeat: the patch was already adapted by an earlier run.
    if marker not in "".join(lines) and sum(line.startswith("+") and user_badge in line for line in lines) == 1 and sum(line.startswith("+") and chat_badge in line for line in lines) == 1:
        print("[OK] Premium badge patch already adapted; both badge additions are present.")
        return
    raise SystemExit("[ERROR] Premium badge patch is in an unknown state; refusing to guess.")


def adapt_archive_media_patch(repo: Path) -> None:
    """Route missing document/photo stock paths through the archive restore helper."""
    import re

    patch = repo / "patches" / "entiny" / "media" / "restore-archived-media.patch"
    if not patch.is_file():
        raise SystemExit("[ERROR] Archived-media patch is missing.")

    original = patch.read_text(encoding="utf-8")
    document_path = (
        "getPathToAttach(MessageObject.getMedia(message).document, null, "
        "forceCache || MessageObject.getMedia(message).ttl_seconds != 0, useFileDatabaseQueue)"
    )
    photo_path = (
        "getPathToAttach(sizeFull, null, "
        "forceCache || MessageObject.getMedia(message).ttl_seconds != 0, useFileDatabaseQueue)"
    )
    document_stock = f"File stock = {document_path};"
    photo_stock = f"File stock = {photo_path};"
    restore = (
        "return stock.exists() ? stock : "
        "desu.inugram.helpers.archive.ArchiveMediaHelper.restoreArchived(currentAccount, message, stock);"
    )

    prefix = original.split("\n---\n", 1)[0].rstrip("\r\n") if "\n---\n" in original else ""
    if not prefix.startswith("From ") or "Subject: preserve and restore archived media" not in prefix:
        raise SystemExit("[ERROR] Archived-media patch header changed; refusing to rewrite it.")

    adapted = (
        prefix + "\n\n---\n"
        " .../src/main/java/org/telegram/messenger/FileLoader.java | 6 ++++--\n"
        " 1 file changed, 4 insertions(+), 2 deletions(-)\n"
        "\n"
        "diff --git a/TMessagesProj/src/main/java/org/telegram/messenger/FileLoader.java "
        "b/TMessagesProj/src/main/java/org/telegram/messenger/FileLoader.java\n"
        "index 0000000..0000000 100644\n"
        "--- a/TMessagesProj/src/main/java/org/telegram/messenger/FileLoader.java\n"
        "+++ b/TMessagesProj/src/main/java/org/telegram/messenger/FileLoader.java\n"
        "@@ -1299,3 +1299,4 @@ public class FileLoader extends BaseController {\n"
        "             if (MessageObject.getMedia(message) instanceof TLRPC.TL_messageMediaDocument) {\n"
        f"-                return {document_path};\n"
        f"+                {document_stock}\n"
        f"+                {restore}\n"
        "             } else if (MessageObject.getMedia(message) instanceof TLRPC.TL_messageMediaPhoto) {\n"
        "@@ -1304,4 +1305,5 @@ public class FileLoader extends BaseController {\n"
        "                     TLRPC.PhotoSize sizeFull = getClosestPhotoSizeWithSize(sizes, AndroidUtilities.getPhotoSize(true), false, null, true);\n"
        "                     if (sizeFull != null) {\n"
        f"-                        return {photo_path};\n"
        f"+                        {photo_stock}\n"
        f"+                        {restore}\n"
        "                     }\n"
    )

    lines = adapted.splitlines()
    for addition in (document_stock, photo_stock):
        if sum(line.startswith("+") and addition in line for line in lines) != 1:
            raise SystemExit("[ERROR] Archived-media stock path calculation is missing or duplicated.")
    if sum(line.startswith("+") and restore in line for line in lines) != 2:
        raise SystemExit("[ERROR] Archived-media restoration is not present in both media branches.")
    if "res.exists()" in adapted or "restoreArchived(currentAccount, message, res)" in adapted:
        raise SystemExit("[ERROR] Legacy archived-media patch logic remains.")

    hunk_headers = [i for i, line in enumerate(lines) if line.startswith("@@ -")]
    if len(hunk_headers) != 2:
        raise SystemExit("[ERROR] Unexpected archived-media hunk count.")
    for index, hunk_start in enumerate(hunk_headers):
        match = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@", lines[hunk_start])
        if not match:
            raise SystemExit("[ERROR] Invalid archived-media hunk header.")
        hunk_end = hunk_headers[index + 1] if index + 1 < len(hunk_headers) else len(lines)
        body = lines[hunk_start + 1:hunk_end]
        old_count = sum(line.startswith((" ", "-")) for line in body)
        new_count = sum(line.startswith((" ", "+")) for line in body)
        if old_count != int(match.group(2)) or new_count != int(match.group(4)):
            raise SystemExit("[ERROR] Archived-media hunk lengths do not match their headers.")

    already_adapted = (
        original.count(document_stock) == 1
        and original.count(photo_stock) == 1
        and original.count(restore) == 2
        and "restoreArchived(currentAccount, message, res)" not in original
    )
    if original == adapted:
        print("[OK] Archived-media patch already adapted; document and photo restoration remain enabled.")
    elif already_adapted:
        patch.write_text(adapted, encoding="utf-8")
        print("[OK] Archived-media patch formatting normalized; both media branches remain enabled.")
    else:
        legacy_restore = "desu.inugram.helpers.archive.ArchiveMediaHelper.restoreArchived(currentAccount, message, res)"
        if original.count(legacy_restore) != 2:
            raise SystemExit("[ERROR] Archived-media patch is in an unknown state; refusing to guess.")
        patch.write_text(adapted, encoding="utf-8")
        print("[OK] Archived-media patch adapted for delegated stock paths.")
    print("[OK] Stock getPathToAttach arguments, account/message identity and fallback preserved.")


def adapt_ios_input_bar_patch(repo: Path) -> None:
    """Remove translator-only menu code while retaining the iOS input-bar patch."""
    import re

    patch = repo / "patches" / "entiny" / "chat" / "ios-input-bar.patch"
    series = repo / "series"
    if not patch.is_file() or not series.is_file():
        raise SystemExit("[ERROR] iOS input-bar patch or active series is missing.")
    active = {line.strip().replace("\\", "/") for line in series.read_text(encoding="utf-8").splitlines()}
    if "entiny/translator/input-translate.patch" in active:
        raise SystemExit("[ERROR] Translator patch is active; refusing to remove its input-menu integration.")

    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)
    menu_helper = "desu.inugram.helpers.chat.ChatInputMenuHelper"
    visible_marker = menu_helper + ".isMenuButtonVisible(this)"
    menu_marker = menu_helper + ".getMenuButton(this)"
    set_inset = "IosInputHelper.setInputMenuButtonIconInset"
    menu_offset = "IosInputHelper.getInputMenuButtonOffsetDp"
    old_translation = "inu_menuBtn.setTranslationX(hasScheduled ? -dp(48) : 0);"
    joined = "".join(lines)

    def hunk_end(index: int) -> int:
        return next(
            (i for i in range(index + 1, len(lines))
             if lines[i].startswith("@@ -") or lines[i].startswith("diff --git ")),
            len(lines),
        )

    hunks = []
    for index, line in enumerate(lines):
        if line.startswith("@@ -"):
            end_index = hunk_end(index)
            body = lines[index + 1:end_index]
            file_index = max((i for i in range(index) if lines[i].startswith("diff --git ")), default=-1)
            hunks.append((index, end_index, body, file_index))

    translator_hunks = [
        hunk for hunk in hunks
        if any(menu_helper in line for line in hunk[2])
    ]
    if not translator_hunks:
        if any(marker in joined for marker in (menu_helper, set_inset, menu_offset)):
            raise SystemExit("[ERROR] iOS input-bar patch has an unknown translator integration state.")
        print("[OK] iOS input-bar patch already adapted; translator-only menu code remains excluded.")
        return
    if len(translator_hunks) != 2:
        raise SystemExit("[ERROR] Expected two translator-dependent iOS input-bar hunks.")

    added_menu_hunks = [
        hunk for hunk in translator_hunks
        if any(line.startswith("+") and visible_marker in line for line in hunk[2])
    ]
    replaced_menu_hunks = [
        hunk for hunk in translator_hunks
        if any(line.startswith("-") and old_translation in line for line in hunk[2])
    ]
    if len(added_menu_hunks) != 1 or len(replaced_menu_hunks) != 1:
        raise SystemExit("[ERROR] Could not distinguish translator-only iOS input-bar hunks.")
    added_hunk = added_menu_hunks[0]
    replaced_hunk = replaced_menu_hunks[0]
    if added_hunk[3] != replaced_hunk[3] or "ChatActivityEnterView.java" not in lines[added_hunk[3]]:
        raise SystemExit("[ERROR] Translator-only hunks are not in the expected Java file.")
    if added_hunk[0] >= replaced_hunk[0]:
        raise SystemExit("[ERROR] Translator-only hunk order changed; refusing to guess.")

    additions_to_remove: set[int] = set()
    body_start = added_hunk[0] + 1
    body_end = added_hunk[1]
    visible_lines = [
        i for i in range(body_start, body_end)
        if lines[i].startswith("+") and visible_marker in lines[i]
    ]
    if len(visible_lines) != 1:
        raise SystemExit("[ERROR] Expected one translator menu visibility branch.")
    branch_start = visible_lines[0]
    expected_branch = (
        "+            } else if (" + visible_marker + ") {",
        "+                fieldRightMarginDp += DEFAULT_HEIGHT + iosGapDp;",
        "+            }",
    )
    if tuple(line.rstrip("\r\n") for line in lines[branch_start:branch_start + 3]) != expected_branch:
        raise SystemExit("[ERROR] Translator menu visibility branch changed; refusing to alter nearby iOS layout.")
    additions_to_remove.update(range(branch_start, branch_start + 3))

    menu_lines = [
        i for i in range(body_start, body_end)
        if lines[i].startswith("+") and menu_marker in lines[i]
    ]
    if len(menu_lines) != 1:
        raise SystemExit("[ERROR] Expected one added translator menu button block.")
    menu_start = menu_lines[0]
    expected_menu_block = (
        "+            View inu_menuBtn = " + menu_marker + ";",
        "+            if (inu_menuBtn != null) {",
        "+                desu.inugram.helpers.chat.IosInputHelper.setInputMenuButtonIconInset(inu_menuBtn, hasInsideRightIcon);",
        "+                inu_menuBtn.setTranslationX(dp(desu.inugram.helpers.chat.IosInputHelper.getInputMenuButtonOffsetDp(hasInsideRightIcon, DEFAULT_HEIGHT, iosGapDp)));",
        "+            }",
    )
    if tuple(line.rstrip("\r\n") for line in lines[menu_start:menu_start + 5]) != expected_menu_block:
        raise SystemExit("[ERROR] Translator menu button block changed; refusing to alter nearby iOS layout.")
    additions_to_remove.update(range(menu_start, menu_start + 5))
    if len(additions_to_remove) != 8:
        raise SystemExit("[ERROR] Unexpected translator-only addition count.")

    header = lines[added_hunk[0]].rstrip("\r\n")
    match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$", header)
    if not match:
        raise SystemExit("[ERROR] Invalid translator-only iOS hunk header.")
    old_count = int(match.group(2) or 1)
    new_count = int(match.group(4) or 1)
    if (
        sum(line.startswith((" ", "-")) for line in added_hunk[2]) != old_count
        or sum(line.startswith((" ", "+")) for line in added_hunk[2]) != new_count
    ):
        raise SystemExit("[ERROR] Translator-only iOS hunk lengths do not match their header.")

    replace_lines: dict[int, str] = {
        added_hunk[0]: (
            f"@@ -{match.group(1)},{old_count} +{match.group(3)},{new_count - 8} @@{match.group(5)}\n"
        )
    }
    replaced_header = lines[replaced_hunk[0]].rstrip("\r\n")
    replaced_match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$", replaced_header)
    if not replaced_match:
        raise SystemExit("[ERROR] Invalid translator-menu replacement hunk header.")
    replaced_old = int(replaced_match.group(2) or 1)
    replaced_new = int(replaced_match.group(4) or 1)
    replaced_body = replaced_hunk[2]
    added = sum(line.startswith("+") for line in replaced_body)
    deleted = sum(line.startswith("-") for line in replaced_body)
    if (
        sum(line.startswith((" ", "-")) for line in replaced_body) != replaced_old
        or sum(line.startswith((" ", "+")) for line in replaced_body) != replaced_new
        or (added, deleted) != (3, 1)
        or not any(line.startswith(" ") and menu_marker in line for line in replaced_body)
    ):
        raise SystemExit("[ERROR] Translator-menu replacement hunk changed; refusing to remove it.")

    file_start = added_hunk[3]
    file_end = next(
        (i for i in range(replaced_hunk[1], len(lines)) if lines[i].startswith("diff --git ")),
        len(lines),
    )
    later_hunks = [hunk for hunk in hunks if replaced_hunk[0] < hunk[0] < file_end]
    for later in later_hunks:
        later_match = re.match(
            r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$",
            lines[later[0]].rstrip("\r\n"),
        )
        if not later_match:
            raise SystemExit("[ERROR] Invalid following iOS input-bar hunk header.")
        shift = 10  # eight removed additions, then the removed hunk's net +2 lines
        new_start = int(later_match.group(3)) - shift
        if new_start < 1:
            raise SystemExit("[ERROR] Invalid shifted iOS input-bar hunk position.")
        replace_lines[later[0]] = (
            f"@@ -{later_match.group(1)},{later_match.group(2) or 1} "
            f"+{new_start},{later_match.group(4) or 1} @@{later_match.group(5)}\n"
        )

    remove_lines = set(additions_to_remove) | set(range(replaced_hunk[0], replaced_hunk[1]))
    lines = [replace_lines.get(i, line) for i, line in enumerate(lines) if i not in remove_lines]

    first_diff = next((i for i, line in enumerate(lines) if line.startswith("diff --git ")), -1)
    separator = next((i for i, line in enumerate(lines[:first_diff]) if line.rstrip("\r\n") == "---"), -1)
    if first_diff < 0 or separator < 0:
        raise SystemExit("[ERROR] iOS input-bar patch summary header is malformed.")
    stats = lines[separator + 1:first_diff]
    target_rows = [i for i, line in enumerate(stats) if "ChatActivityEnterView.java" in line and "|" in line]
    summary_rows = [i for i, line in enumerate(stats) if "files changed" in line]
    if len(target_rows) != 1 or len(summary_rows) != 1:
        raise SystemExit("[ERROR] iOS input-bar diff summary rows are ambiguous.")
    row = stats[target_rows[0]].rstrip("\r\n")
    row_match = re.match(r"^(\s*.*?\|\s*)(\d+)(?:\s+.*)?$", row)
    if not row_match or int(row_match.group(2)) < len(additions_to_remove) + added + deleted:
        raise SystemExit("[ERROR] Invalid iOS input-bar file summary row.")
    stats[target_rows[0]] = f"{row_match.group(1)}{int(row_match.group(2)) - len(additions_to_remove) - added - deleted}\n"
    summary = stats[summary_rows[0]].rstrip("\r\n")
    summary_match = re.match(
        r"^(\s*)(\d+) files changed, (\d+) insertions\(\+\), (\d+) deletions\(-\)$",
        summary,
    )
    total_removed_additions = len(additions_to_remove) + added
    if not summary_match or int(summary_match.group(3)) < total_removed_additions or int(summary_match.group(4)) < deleted:
        raise SystemExit("[ERROR] Invalid iOS input-bar patch summary totals.")
    stats[summary_rows[0]] = (
        f"{summary_match.group(1)}{summary_match.group(2)} files changed, "
        f"{int(summary_match.group(3)) - total_removed_additions} insertions(+), "
        f"{int(summary_match.group(4)) - deleted} deletions(-)\n"
    )
    lines = lines[:separator + 1] + stats + lines[first_diff:]

    result = "".join(lines)
    if any(marker in result for marker in (menu_helper, set_inset, menu_offset)):
        raise SystemExit("[ERROR] Translator-only ChatInputMenuHelper integration remains in iOS input-bar patch.")
    for index, line in enumerate(lines):
        if not line.startswith("@@ -"):
            continue
        hunk_match = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@", line)
        if not hunk_match:
            raise SystemExit("[ERROR] Invalid recalculated iOS input-bar hunk header.")
        end_index = next(
            (i for i in range(index + 1, len(lines))
             if lines[i].startswith("@@ -") or lines[i].startswith("diff --git ")),
            len(lines),
        )
        body = lines[index + 1:end_index]
        if (
            sum(item.startswith((" ", "-")) for item in body) != int(hunk_match.group(2))
            or sum(item.startswith((" ", "+")) for item in body) != int(hunk_match.group(4))
        ):
            raise SystemExit("[ERROR] Recalculated iOS input-bar hunk length mismatch.")

    patch.write_text(result, encoding="utf-8")
    print("[OK] Translator-only ChatInputMenuHelper code removed from iOS input-bar patch.")
    print("[OK] Remaining iOS input-bar changes and hunk positions recalculated.")

def adapt_burn_voice_round_patch(repo: Path) -> None:
    """Drop excluded self-destruct context while preserving one-time voice/video expiry."""
    import re

    patch = repo / "patches" / "entiny" / "media" / "burn-voice-round.patch"
    if not patch.is_file():
        raise SystemExit("[ERROR] Burn voice/round patch is missing.")

    original = patch.read_text(encoding="utf-8")
    old_condition = (
        "messageObject == null || messageObject.isOut() || !messageObject.isSecretMedia() "
        "|| messageObject.messageOwner.ttl != 0x7FFFFFFF"
    )
    new_condition = (
        "messageObject == null || messageObject.isOut() || !messageObject.isSecretMedia() "
        "&& (messageObject.messageOwner.media == null || messageObject.messageOwner.media.ttl_seconds == 0) "
        "|| messageObject.messageOwner.ttl != 0x7FFFFFFF"
    )
    prefix = original.split("\n---\n", 1)[0].rstrip("\r\n") if "\n---\n" in original else ""
    if not prefix.startswith("From ") or "Subject: burn one-time voice and round videos" not in prefix:
        raise SystemExit("[ERROR] Burn voice/round patch header changed; refusing to rewrite it.")

    adapted = (
        prefix + "\n\n---\n"
        " TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java | 2 +-\n"
        " 1 file changed, 1 insertion(+), 1 deletion(-)\n"
        "\n"
        "diff --git a/TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java "
        "b/TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java\n"
        "index 0000000..0000000 100644\n"
        "--- a/TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java\n"
        "+++ b/TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java\n"
        "@@ -15787,4 +15787,4 @@ public class ChatActivity extends BaseFragment implements\n"
        "     private Runnable sendSecretMediaDelete(MessageObject messageObject) {\n"
        f"-        if ({old_condition}) {{\n"
        f"+        if ({new_condition}) {{\n"
        "             return null;\n"
        "         }\n"
    )

    lines = adapted.splitlines()
    headers = [i for i, line in enumerate(lines) if line.startswith("@@ -")]
    if len(headers) != 1:
        raise SystemExit("[ERROR] Unexpected burn voice/round hunk count.")
    match = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@", lines[headers[0]])
    if not match:
        raise SystemExit("[ERROR] Invalid burn voice/round hunk header.")
    body = lines[headers[0] + 1:]
    if (
        sum(line.startswith((" ", "-")) for line in body) != int(match.group(2))
        or sum(line.startswith((" ", "+")) for line in body) != int(match.group(4))
        or sum(line.startswith("-") and old_condition in line for line in body) != 1
        or sum(line.startswith("+") and new_condition in line for line in body) != 1
    ):
        raise SystemExit("[ERROR] Burn voice/round hunk context or lengths are invalid.")

    if original == adapted:
        print("[OK] Burn voice/round patch already adapted; one-time media expiry remains enabled.")
    else:
        if (
            original.count("public Runnable sendSecretMediaDelete(MessageObject messageObject)") != 1
            or original.count("SelfDestructHelper.shouldPreserveMedia(dialog_id)") != 1
            or original.count(old_condition) != 1
            or original.count(new_condition) != 1
        ):
            raise SystemExit("[ERROR] Burn voice/round patch is in an unknown state; refusing to guess.")
        patch.write_text(adapted, encoding="utf-8")
        print("[OK] Burn voice/round patch adapted without the excluded self-destruct context.")
    print("[OK] One-time voice and round-video expiry condition preserved.")


def adapt_feed_chatactivity_patch(repo: Path) -> None:
    """Remove ghost-mode and reaction-sync context from the independent feed patch."""
    import re

    patch = repo / "patches" / "entiny" / "feed" / "feed-chatactivity.patch"
    series = repo / "series"
    if not patch.is_file() or not series.is_file():
        raise SystemExit("[ERROR] Feed ChatActivity patch or active series is missing.")
    active = {line.strip().replace("\\", "/") for line in series.read_text(encoding="utf-8").splitlines()}
    if "entiny/privacy/ghost-mode.patch" in active or "entiny/chat/reaction-read-sync.patch" in active:
        raise SystemExit("[ERROR] Excluded privacy/reaction patch is active; refusing to remove its context.")

    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)

    def records(source: list[str]) -> list[tuple[int, int, int, list[str]]]:
        found = []
        for index, line in enumerate(source):
            if not line.startswith("@@ -"):
                continue
            end = next(
                (i for i in range(index + 1, len(source))
                 if source[i].startswith("@@ -") or source[i].startswith("diff --git ")),
                len(source),
            )
            file_index = max((i for i in range(index) if source[i].startswith("diff --git ")), default=-1)
            found.append((index, end, file_index, source[index + 1:end]))
        return found

    original_hunks = records(lines)
    joined = "".join(lines)
    ghost_context = "desu.inugram.helpers.security.GhostHelper.processSendRequest"
    keep_reactions = "getMessagesController().inu_keepReadReactions(did, msgId"
    consume_reactions = "inu_consumePendingJumpReactions(messageObject);"
    translation_context = "desu.inugram.helpers.translate.TranslateHelper.carryTranslation(old, messageObject);"
    normalize_call = "desu.inugram.helpers.feed.FeedRequestNormalizer.normalize(currentAccount, object);"
    if (
        ghost_context not in joined
        and keep_reactions not in joined
        and consume_reactions not in joined
        and translation_context not in joined
        and sum(line.startswith("+") and normalize_call in line for line in lines) == 1
    ):
        print("[OK] Feed ChatActivity patch already adapted; feed request/reaction updates remain enabled.")
        return

    connection_hunks = [
        hunk for hunk in original_hunks
        if hunk[2] >= 0 and "ConnectionsManager.java" in lines[hunk[2]]
        and any(ghost_context in line for line in hunk[3])
    ]
    reaction_context_hunks = [
        hunk for hunk in original_hunks
        if hunk[2] >= 0 and "ChatActivity.java" in lines[hunk[2]]
        and any(keep_reactions in line for line in hunk[3])
    ]
    update_hunks = [
        hunk for hunk in original_hunks
        if hunk[2] >= 0 and "ChatActivity.java" in lines[hunk[2]]
        and any(line.startswith("+") and "getMessageObjectForUpdate(did, msgId)" in line for line in hunk[3])
    ]
    translation_hunks = [
        hunk for hunk in original_hunks
        if hunk[2] >= 0 and "ChatActivity.java" in lines[hunk[2]]
        and any(translation_context in line for line in hunk[3])
    ]
    if (
        "entiny/translator/input-translate.patch" in active
        or len(connection_hunks) != 1
        or len(reaction_context_hunks) != 1
        or len(update_hunks) != 1
        or len(translation_hunks) != 1
    ):
        raise SystemExit("[ERROR] Feed patch excluded-context hunks are ambiguous or changed.")

    connection = connection_hunks[0]
    if sum(line.startswith("+") and normalize_call in line for line in connection[3]) != 1:
        raise SystemExit("[ERROR] Feed request normalizer addition is missing or duplicated.")
    connection_replacement = [
        "@@ -402,3 +402,4 @@ public class ConnectionsManager extends BaseController {\n",
        "         try {\n",
        "             NativeByteBuffer buffer = new NativeByteBuffer(object.getObjectSize());\n",
        "             object.serializeToStream(buffer);\n",
    ]
    connection_replacement.insert(1, f"+        {normalize_call}\n")

    def remove_context(
        hunk: tuple[int, int, int, list[str]],
        markers: tuple[str, ...],
        start_shift: int = 0,
    ) -> list[str]:
        header = lines[hunk[0]].rstrip("\r\n")
        match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$", header)
        if not match:
            raise SystemExit("[ERROR] Invalid feed ChatActivity hunk header.")
        body = list(hunk[3])
        remove_indexes = set()
        for marker in markers:
            matches = [i for i, line in enumerate(body) if marker in line]
            if len(matches) != 1 or not body[matches[0]].startswith(" "):
                raise SystemExit("[ERROR] Expected excluded-only feed patch context is missing or changed.")
            remove_indexes.add(matches[0])
        body = [line for i, line in enumerate(body) if i not in remove_indexes]
        old_count = sum(line.startswith((" ", "-")) for line in body)
        new_count = sum(line.startswith((" ", "+")) for line in body)
        if old_count < 1 or new_count < 1:
            raise SystemExit("[ERROR] Invalid feed ChatActivity hunk after context removal.")
        return [
            f"@@ -{int(match.group(1)) + start_shift},{old_count} "
            f"+{int(match.group(3)) + start_shift},{new_count} @@{match.group(5)}\n",
            *body,
        ]

    reaction_hunk = reaction_context_hunks[0]
    reaction_replacement = remove_context(reaction_hunk, (keep_reactions,))
    update_hunk = update_hunks[0]
    update_replacement = remove_context(
        update_hunk,
        ("invalidateMessagesVisiblePart();", "if (did == dialog_id) {", consume_reactions),
    )

    if update_hunk[0] <= reaction_hunk[0]:
        raise SystemExit("[ERROR] Feed reaction hunk order changed; refusing to guess.")

    reaction_header = lines[reaction_hunk[0]].rstrip("\r\n")
    reaction_match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$", reaction_header)
    preceding_context = "            long did = (Long) args[0];"
    if not reaction_match or not any(
        line.startswith(" ") and "doOnIdle(() -> {" in line
        for line in reaction_replacement[1:]
    ):
        raise SystemExit("[ERROR] Stable feed reaction context is missing or changed.")
    combined_body = [
        f" {preceding_context}\n",
        *reaction_replacement[1:],
        "                         messageObject.forceUpdate = true;\n",
        *update_replacement[1:],
        "                 }\n",
        "             });\n",
        "         } else if (id == NotificationCenter.savedReactionTagsUpdate) {\n",
    ]
    old_count = sum(line.startswith((" ", "-")) for line in combined_body)
    new_count = sum(line.startswith((" ", "+")) for line in combined_body)
    combined_replacement = [
        f"@@ -{int(reaction_match.group(1)) - 1},{old_count} "
        f"+{int(reaction_match.group(3)) - 1},{new_count} @@{reaction_match.group(5)}\n",
        *combined_body,
    ]

    replacements = {
        connection[0]: (connection[1], connection_replacement),
        reaction_hunk[0]: (update_hunk[1], combined_replacement),
    }
    translation_hunk = translation_hunks[0]
    translation_replacement = remove_context(translation_hunk, (translation_context,), start_shift=-1)
    replacements[translation_hunk[0]] = (translation_hunk[1], translation_replacement)
    downstream_shift = -4  # one omitted reaction-sync line before this hunk and three in it
    for hunk in original_hunks:
        if (
            hunk[0] <= update_hunk[0]
            or hunk[0] == translation_hunk[0]
            or hunk[2] < 0
            or "ChatActivity.java" not in lines[hunk[2]]
        ):
            continue
        header = lines[hunk[0]].rstrip("\r\n")
        match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$", header)
        if not match:
            raise SystemExit("[ERROR] Invalid downstream feed ChatActivity hunk header.")
        translation_shift = -1 if hunk[0] > translation_hunk[0] else 0
        old_start = int(match.group(1)) + downstream_shift + translation_shift
        new_start = int(match.group(3)) + downstream_shift + translation_shift
        if old_start < 1 or new_start < 1:
            raise SystemExit("[ERROR] Invalid downstream feed ChatActivity hunk position.")
        replacements[hunk[0]] = (
            hunk[1],
            [
                f"@@ -{old_start},{match.group(2) or 1} "
                f"+{new_start},{match.group(4) or 1} @@{match.group(5)}\n",
                *hunk[3],
            ],
        )
    result = []
    index = 0
    while index < len(lines):
        if index in replacements:
            end, replacement = replacements[index]
            result.extend(replacement)
            index = end
        else:
            result.append(lines[index])
            index += 1

    text = "".join(result)
    if any(marker in text for marker in (ghost_context, keep_reactions, consume_reactions, translation_context)):
        raise SystemExit("[ERROR] Excluded ghost/reaction context remains in feed patch.")
    if sum(line.startswith("+") and normalize_call in line for line in result) != 1:
        raise SystemExit("[ERROR] Feed request normalizer addition was not preserved exactly.")
    for index, line in enumerate(result):
        if not line.startswith("@@ -"):
            continue
        match = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@", line)
        if not match:
            raise SystemExit("[ERROR] Invalid recalculated feed patch hunk header.")
        end = next(
            (i for i in range(index + 1, len(result))
             if result[i].startswith("@@ -") or result[i].startswith("diff --git ")),
            len(result),
        )
        body = result[index + 1:end]
        if (
            sum(item.startswith((" ", "-")) for item in body) != int(match.group(2))
            or sum(item.startswith((" ", "+")) for item in body) != int(match.group(4))
        ):
            raise SystemExit("[ERROR] Recalculated feed patch hunk length mismatch.")

    patch.write_text("".join(result), encoding="utf-8")
    print("[OK] Feed patch adapted without ghost-mode or reaction-read-sync context.")
    print("[OK] Feed request normalization and reaction-update handling remain enabled.")


def adapt_input_menu_reserve_patch(repo: Path) -> None:
    """Retarget the input-menu reserve hunk to pinned source without translator context."""
    import re

    patch = repo / "patches" / "entiny" / "chat" / "input-menu-reserve.patch"
    series = repo / "series"
    if not patch.is_file() or not series.is_file():
        raise SystemExit("[ERROR] Input-menu reserve patch or active series is missing.")
    active = {line.strip().lower().replace("\\", "/") for line in series.read_text(encoding="utf-8").splitlines()}
    if any("input-translate" in entry for entry in active):
        raise SystemExit("[ERROR] Excluded input-translate patch is active; refusing to adapt its context.")

    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)
    joined = "".join(lines)
    menu_check = "desu.inugram.helpers.chat.ChatInputMenuHelper.isMenuButtonVisible(this)"
    if (
        re.search(r"^@@ -9380,6 \+9380,9 @@", joined, re.MULTILINE)
        and sum(line.startswith("+") and menu_check in line for line in lines) == 1
        and not any(line.startswith(" ") and menu_check in line for line in lines)
    ):
        print("[OK] Input-menu reserve patch already adapted; menu spacing remains enabled.")
        return

    hunk_indexes = [index for index, line in enumerate(lines) if line.startswith("@@ -")]
    if (
        len(hunk_indexes) != 1
        or "ChatActivityEnterView.java" not in joined
        or sum(line.startswith("+") and menu_check in line for line in lines) != 1
        or sum(line.startswith(" ") and menu_check in line for line in lines) != 1
        or sum("layoutParams.rightMargin = dp(98);" in line for line in lines) < 1
    ):
        raise SystemExit("[ERROR] Input-menu reserve patch context is ambiguous or changed.")

    start = hunk_indexes[0]
    replacement = [
        "@@ -9380,6 +9380,9 @@ public class ChatActivityEnterView extends FrameLayout implements\n",
        "             } else {\n",
        "                 layoutParams.rightMargin = dp(50);\n",
        "             }\n",
        f"+            if ({menu_check}) {{\n",
        "+                layoutParams.rightMargin += dp(48);\n",
        "+            }\n",
        "         } else {\n",
        "             if (scheduledButton != null && scheduledButton.getTag() != null) {\n",
        "                 layoutParams.rightMargin = dp(50);\n",
    ]
    result = lines[:start] + replacement
    if (
        sum(line.startswith((" ", "-")) for line in replacement[1:]) != 6
        or sum(line.startswith((" ", "+")) for line in replacement[1:]) != 9
        or sum(line.startswith("+") and menu_check in line for line in result) != 1
    ):
        raise SystemExit("[ERROR] Rebuilt input-menu reserve hunk has invalid counts or behavior.")
    patch.write_text("".join(result), encoding="utf-8")
    print("[OK] Input-menu reserve hunk retargeted without input-translate context.")
    print("[OK] Menu-button spacing remains enabled.")


def adapt_local_names_patch(repo: Path) -> None:
    """Drop the local-premium-only context from the independent local-name patch."""
    import re

    patch = repo / "patches" / "entiny" / "ui" / "local-names.patch"
    series = repo / "series"
    if not patch.is_file() or not series.is_file():
        raise SystemExit("[ERROR] Local-names patch or active series is missing.")
    active = {line.strip().lower().replace("\\", "/") for line in series.read_text(encoding="utf-8").splitlines()}
    if any("local-premium" in entry for entry in active):
        raise SystemExit("[ERROR] Excluded local-premium patch is active; refusing to adapt its context.")

    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)
    marker = "desu.inugram.helpers.LocalPremiumHelper.applyToSelfUser(user, currentAccount);"
    addition = "desu.inugram.helpers.profile.LocalNameHelper.applyTo(user, currentAccount);"
    if marker not in "".join(lines):
        if sum(line.startswith("+") and addition in line for line in lines) == 1:
            print("[OK] Local-names patch already adapted; local profile names remain enabled.")
            return
        raise SystemExit("[ERROR] Local-names patch is in an unknown state; refusing to guess.")

    marker_lines = [index for index, line in enumerate(lines) if marker in line]
    if len(marker_lines) != 1 or not lines[marker_lines[0]].startswith(" "):
        raise SystemExit("[ERROR] Local-premium context in local-names patch is ambiguous or changed.")
    target_hunk = next(
        (hunk for hunk in range(marker_lines[0] - 1, -1, -1) if lines[hunk].startswith("@@ -")),
        -1,
    )
    target_file = max(
        (index for index in range(target_hunk) if lines[index].startswith("diff --git ")),
        default=-1,
    )
    if target_hunk < 0 or target_file < 0 or "MessagesController.java" not in lines[target_file]:
        raise SystemExit("[ERROR] Local-names context is outside the expected MessagesController hunk.")

    def hunk_end(index: int) -> int:
        return next(
            (i for i in range(index + 1, len(lines))
             if lines[i].startswith("@@ -") or lines[i].startswith("diff --git ")),
            len(lines),
        )

    header = lines[target_hunk].rstrip("\r\n")
    match = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@(.*)$", header)
    end = hunk_end(target_hunk)
    body = list(lines[target_hunk + 1:end])
    context_indexes = [index for index, line in enumerate(body) if marker in line]
    if not match or len(context_indexes) != 1 or not body[context_indexes[0]].startswith(" "):
        raise SystemExit("[ERROR] Local-names hunk header or context is invalid.")
    body.pop(context_indexes[0])
    old_count = sum(line.startswith((" ", "-")) for line in body)
    new_count = sum(line.startswith((" ", "+")) for line in body)
    replacements = {
        target_hunk: (
            end,
            [
                f"@@ -{match.group(1)},{old_count} +{match.group(3)},{new_count} @@{match.group(5)}\n",
                *body,
            ],
        )
    }

    file_end = next(
        (index for index in range(target_file + 1, len(lines)) if lines[index].startswith("diff --git ")),
        len(lines),
    )
    for index in range(target_hunk + 1, file_end):
        if not lines[index].startswith("@@ -"):
            continue
        later = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@(.*)$", lines[index].rstrip("\r\n"))
        if not later:
            raise SystemExit("[ERROR] Later local-names hunk header is invalid.")
        replacements[index] = (
            hunk_end(index),
            [
                f"@@ -{int(later.group(1)) - 1},{later.group(2)} "
                f"+{int(later.group(3)) - 1},{later.group(4)} @@{later.group(5)}\n",
                *lines[index + 1:hunk_end(index)],
            ],
        )

    result = []
    index = 0
    while index < len(lines):
        if index in replacements:
            end, replacement = replacements[index]
            result.extend(replacement)
            index = end
        else:
            result.append(lines[index])
            index += 1
    text = "".join(result)
    if marker in text or sum(line.startswith("+") and addition in line for line in result) != 1:
        raise SystemExit("[ERROR] Local-names patch still contains excluded context or lost its behavior.")
    for index, line in enumerate(result):
        if not line.startswith("@@ -"):
            continue
        counts = re.match(r"^@@ -\d+,(\d+) \+\d+,(\d+) @@", line)
        end = next(
            (i for i in range(index + 1, len(result))
             if result[i].startswith("@@ -") or result[i].startswith("diff --git ")),
            len(result),
        )
        body = result[index + 1:end]
        if (
            not counts
            or sum(item.startswith((" ", "-")) for item in body) != int(counts.group(1))
            or sum(item.startswith((" ", "+")) for item in body) != int(counts.group(2))
        ):
            raise SystemExit("[ERROR] Local-names patch hunk counts are invalid after adaptation.")
    patch.write_text(text, encoding="utf-8")
    print("[OK] Local-names patch adapted without local-premium context.")
    print("[OK] Local profile name and avatar behavior remains enabled.")


def adapt_system_folders_patch(repo: Path) -> None:
    """Keep system-folder matching without the excluded folder-membership context."""
    import re

    patch = repo / "patches" / "entiny" / "tabs" / "system-folders.patch"
    series = repo / "series"
    if not patch.is_file() or not series.is_file():
        raise SystemExit("[ERROR] System-folders patch or active series is missing.")
    active = {line.strip().lower().replace("\\", "/") for line in series.read_text(encoding="utf-8").splitlines()}
    if any("unlimited-folder-chats" in entry for entry in active):
        raise SystemExit("[ERROR] Excluded folder-membership restriction patch is active; refusing to adapt its context.")

    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)
    membership_context = "desu.inugram.helpers.dialogs.FolderMembershipHelper.isLocallyIncluded("
    administrator_check = "desu.inugram.helpers.dialogs.SystemFoldersHelper.isAdministratorFolder(id)"
    administrator_match = "desu.inugram.helpers.dialogs.SystemFoldersHelper.matchesAdministrator(accountInstance.getCurrentAccount(), dialogId)"
    if membership_context not in "".join(lines):
        if (
            sum(line.startswith("+") and administrator_check in line for line in lines) == 1
            and sum(line.startswith("+") and administrator_match in line for line in lines) == 1
        ):
            print("[OK] System-folders patch already adapted; administrator folder matching remains enabled.")
            return
        raise SystemExit("[ERROR] System-folders patch is in an unknown state; refusing to guess.")

    marker_lines = [index for index, line in enumerate(lines) if membership_context in line]
    target_hunk = next(
        (hunk for hunk in range(marker_lines[0] - 1, -1, -1) if lines[hunk].startswith("@@ -")),
        -1,
    ) if len(marker_lines) == 1 else -1
    target_file = max(
        (index for index in range(target_hunk) if lines[index].startswith("diff --git ")),
        default=-1,
    )
    if (
        target_hunk < 0
        or target_file < 0
        or "MessagesController.java" not in lines[target_file]
        or not lines[marker_lines[0]].startswith(" ")
    ):
        raise SystemExit("[ERROR] Folder-membership context is ambiguous or outside MessagesController.")

    end = next(
        (index for index in range(target_hunk + 1, len(lines))
         if lines[index].startswith("@@ -") or lines[index].startswith("diff --git ")),
        len(lines),
    )
    header = lines[target_hunk].rstrip("\r\n")
    match = re.match(r"^@@ -\d+,\d+ \+\d+,\d+ @@(.*)$", header)
    if not match:
        raise SystemExit("[ERROR] System-folders MessagesController hunk header is invalid.")
    replacement = [
        f"@@ -1314,6 +1314,9 @@{match.group(1)}\n",
        "             if (alwaysShow.contains(dialogId)) {\n",
        "                 return true;\n",
        "+            }\n",
        f"+            if ({administrator_check}) {{\n",
        f"+                return {administrator_match};\n",
        "             }\n",
        "             if (d.folder_id != 0 && (flags & DIALOG_FILTER_FLAG_EXCLUDE_ARCHIVED) != 0) {\n",
        "                 return false;\n",
        "             }\n",
    ]
    result = lines[:target_hunk] + replacement + lines[end:]
    if (
        membership_context in "".join(result)
        or sum(line.startswith("+") and administrator_check in line for line in result) != 1
        or sum(line.startswith("+") and administrator_match in line for line in result) != 1
        or sum(line.startswith((" ", "-")) for line in replacement[1:]) != 6
        or sum(line.startswith((" ", "+")) for line in replacement[1:]) != 9
    ):
        raise SystemExit("[ERROR] System-folders hunk lost behavior or has invalid line counts.")
    patch.write_text("".join(result), encoding="utf-8")
    print("[OK] System-folders patch adapted without folder-membership context.")
    print("[OK] Administrator-folder matching remains enabled.")


def adapt_private_reply_multiline_patch(repo: Path) -> None:
    """Retarget the inaccessible-reply fix without excluded deleted-reply context."""
    import re

    patch = repo / "patches" / "bugfix" / "private-reply-multiline.patch"
    series = repo / "series"
    if not patch.is_file() or not series.is_file():
        raise SystemExit("[ERROR] Private-reply patch or active series is missing.")
    active = {line.strip().lower().replace("\\", "/") for line in series.read_text(encoding="utf-8").splitlines()}
    if any("show-deleted-replies" in entry for entry in active):
        raise SystemExit("[ERROR] Excluded deleted-replies patch is active; refusing to adapt its context.")

    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)
    deleted_reply_context = "!messageObject.inu_isReplyToDeletedMessage()"
    old_expression = "                isReplyQuote = hasReplyQuote && messageObject.messageOwner.reply_to.quote;"
    replacement_expression = (
        "                isReplyQuote = hasReplyQuote && (messageObject.messageOwner.reply_to.quote || "
        "desu.inugram.helpers.chat.ChatHelper.isReplyToInaccessibleChat(currentAccount, messageObject));"
    )
    if deleted_reply_context not in "".join(lines):
        if sum(line.startswith("+") and replacement_expression in line for line in lines) == 1:
            print("[OK] Private-reply patch already adapted; inaccessible-chat quote text remains enabled.")
            return
        raise SystemExit("[ERROR] Private-reply patch is in an unknown state; refusing to guess.")

    hunk_indexes = [index for index, line in enumerate(lines) if line.startswith("@@ -")]
    if (
        len(hunk_indexes) != 1
        or "ChatMessageCell.java" not in "".join(lines)
        or sum(line.startswith("-") and old_expression in line for line in lines) != 1
        or sum(line.startswith("+") and replacement_expression in line for line in lines) != 1
    ):
        raise SystemExit("[ERROR] Private-reply hunk is ambiguous or changed.")
    header = lines[hunk_indexes[0]].rstrip("\r\n")
    match = re.match(r"^@@ -\d+,\d+ \+\d+,\d+ @@(.*)$", header)
    if not match:
        raise SystemExit("[ERROR] Private-reply patch hunk header is invalid.")
    hunk = [
        f"@@ -19474,7 +19474,7 @@{match.group(1)}\n",
        " \n",
        "                 CharSequence name = null;\n",
        "                 hasReplyQuote = messageObject.messageOwner.reply_to != null && (messageObject.messageOwner.reply_to.flags & 64) != 0 && messageObject.messageOwner.reply_to.quote_text != null;\n",
        f"-{old_expression}\n",
        f"+{replacement_expression}\n",
        "                 final boolean showQuote = isReplyQuote && messageObject.messageOwner.reply_to.quote;\n",
        "                 if (isReplyQuote && showQuote && replyQuoteDrawable == null) {\n",
        "                     replyQuoteDrawable = getContext().getResources().getDrawable(R.drawable.mini_quote).mutate();\n",
    ]
    result = lines[:hunk_indexes[0]] + hunk
    if (
        deleted_reply_context in "".join(result)
        or sum(line.startswith("+") and replacement_expression in line for line in result) != 1
        or sum(line.startswith((" ", "-")) for line in hunk[1:]) != 7
        or sum(line.startswith((" ", "+")) for line in hunk[1:]) != 7
    ):
        raise SystemExit("[ERROR] Private-reply hunk lost behavior or has invalid line counts.")
    patch.write_text("".join(result), encoding="utf-8")
    print("[OK] Private-reply patch adapted without deleted-replies context.")
    print("[OK] Inaccessible-chat quote rendering remains enabled.")


def adapt_hide_business_bot_banner_patch(repo: Path) -> None:
    """Retarget the banner toggle without excluded translator-expression context."""
    import re

    patch = repo / "patches" / "entiny" / "chat" / "hide-business-bot-banner.patch"
    series = repo / "series"
    if not patch.is_file() or not series.is_file():
        raise SystemExit("[ERROR] Business-banner patch or active series is missing.")
    active = {line.strip().lower().replace("\\", "/") for line in series.read_text(encoding="utf-8").splitlines()}
    if any("translator/translator.patch" in entry for entry in active):
        raise SystemExit("[ERROR] Excluded translator patch is active; refusing to adapt its context.")

    lines = patch.read_text(encoding="utf-8").splitlines(keepends=True)
    old_expression = "boolean showBizBot = currentEncryptedChat == null && getUserConfig().isPremium()"
    excluded_translator_context = "boolean showTranslate = getMessagesController().getTranslateController().isDialogTranslatable(getDialogId())"
    toggle = "!desu.inugram.InuConfig.HIDE_BUSINESS_BOT_BANNER.getValue()"
    joined = "".join(lines)
    if (
        re.search(r"^@@ -30077,5 \+30077,5 @@", joined, re.MULTILINE)
        and excluded_translator_context not in joined
        and sum(line.startswith("+") and toggle in line for line in lines) == 1
    ):
        print("[OK] Business-banner patch already adapted; the hide toggle remains enabled.")
        return
    if old_expression not in joined:
        raise SystemExit("[ERROR] Business-banner patch is in an unknown state; refusing to guess.")
    if sum(line.startswith("+") and toggle in line for line in lines) != 1 or len(
        [line for line in lines if line.startswith("@@ -")]
    ) != 1:
        raise SystemExit("[ERROR] Business-banner hunk is ambiguous or changed.")
    hunk_index = next(index for index, line in enumerate(lines) if line.startswith("@@ -"))
    header = lines[hunk_index].rstrip("\r\n")
    match = re.match(r"^@@ -\d+,\d+ \+\d+,\d+ @@(.*)$", header)
    if not match:
        raise SystemExit("[ERROR] Business-banner hunk header is invalid.")
    old = "        boolean showBizBot = currentEncryptedChat == null && getUserConfig().isPremium() && preferences.getLong(\"dialog_botid\" + did, 0) != 0 || DEBUG_TOP_PANELS;"
    new = "        boolean showBizBot = !desu.inugram.InuConfig.HIDE_BUSINESS_BOT_BANNER.getValue() && currentEncryptedChat == null && getUserConfig().isPremium() && preferences.getLong(\"dialog_botid\" + did, 0) != 0 || DEBUG_TOP_PANELS;"
    hunk = [
        f"@@ -30077,5 +30077,5 @@{match.group(1)}\n",
        "         ) || DEBUG_TOP_PANELS;\n",
        "         boolean showAddProfilePicture = UserObject.isBot(currentUser) && currentUser.bot_can_edit && currentUser.photo == null;\n",
        f"-{old}\n",
        f"+{new}\n",
        "         boolean showBotAd = currentUser != null && currentUser.bot && messages.size() >= 2 && botSponsoredMessage != null;\n",
        "         if (showRestartTopic) {\n",
    ]
    result = lines[:hunk_index] + hunk
    if (
        sum(line.startswith((" ", "-")) for line in hunk[1:]) != 5
        or sum(line.startswith((" ", "+")) for line in hunk[1:]) != 5
        or sum(line.startswith("+") and toggle in line for line in result) != 1
    ):
        raise SystemExit("[ERROR] Business-banner hunk has invalid counts or lost its toggle.")
    patch.write_text("".join(result), encoding="utf-8")
    print("[OK] Business-banner patch retargeted without translator context.")
    print("[OK] The hide-business-banner toggle remains enabled.")


def adapt_excluded_helper_references(repo: Path) -> None:
    """Keep active helpers buildable without enabling excluded translator/glass patches."""
    import re

    translate = repo / "src" / "fork" / "helpers" / "translate" / "TranslateHelper.kt"
    if not translate.is_file():
        raise SystemExit("[ERROR] Translation helper source is missing.")
    source = translate.read_text(encoding="utf-8")
    old_compare = "MediaDataController.richMessageEquals(oldOwner.rich_message, newOwner.rich_message)"
    new_compare = "richMessagesEqual(oldOwner.rich_message, newOwner.rich_message)"
    compare_helper = (
        "    private fun richMessagesEqual(a: TL_iv.RichMessage?, b: TL_iv.RichMessage?): Boolean {\n"
        "        if (a === b) return true\n"
        "        if (a == null || b == null) return false\n"
        "        return try {\n"
        "            val bufA = SerializedData()\n"
        "            val bufB = SerializedData()\n"
        "            a.serializeToStream(bufA)\n"
        "            b.serializeToStream(bufB)\n"
        "            bufA.toByteArray().contentEquals(bufB.toByteArray())\n"
        "        } catch (e: Exception) {\n"
        "            FileLog.e(e)\n"
        "            false\n"
        "        }\n"
        "    }\n\n"
    )
    carry_marker = "    @JvmStatic\n    fun carryTranslation(old: MessageObject?, updated: MessageObject?) {"
    if source.count(old_compare) == 1 and "private fun richMessagesEqual(" not in source:
        if source.count(carry_marker) != 1:
            raise SystemExit("[ERROR] Translation helper insertion point changed; refusing to guess.")
        for import_line in (
            "import org.telegram.messenger.FileLog\n",
            "import org.telegram.tgnet.SerializedData\n",
            "import org.telegram.tgnet.tl.TL_iv\n",
        ):
            if import_line not in source:
                anchor = "import org.telegram.tgnet.TLRPC\n"
                if source.count(anchor) != 1:
                    raise SystemExit("[ERROR] Translation helper import section changed.")
                source = source.replace(anchor, import_line + anchor, 1)
        source = source.replace(old_compare, new_compare, 1)
        source = source.replace(carry_marker, compare_helper + carry_marker, 1)
        translate.write_text(source, encoding="utf-8")
        print("[OK] Translation helper now compares rich messages without the excluded visibility patch.")
    elif (
        old_compare not in source
        and source.count(new_compare) == 1
        and source.count(compare_helper.rstrip()) == 1
        and all(
            line in source
            for line in (
                "import org.telegram.messenger.FileLog\n",
                "import org.telegram.tgnet.SerializedData\n",
                "import org.telegram.tgnet.tl.TL_iv\n",
            )
        )
    ):
        print("[OK] Translation helper comparison already adapted.")
    else:
        raise SystemExit("[ERROR] Translation helper is in an unknown state; refusing to alter it.")

    ios = repo / "src" / "fork" / "ui" / "settings" / "IosStyleSettingsActivity.kt"
    if not ios.is_file():
        raise SystemExit("[ERROR] iOS style settings source is missing.")
    ios_source = ios.read_text(encoding="utf-8")
    refresh_call = "                    refreshLiquidGlassEffects()\n"
    refresh_method = (
        "    private fun refreshLiquidGlassEffects() {\n"
        "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {\n"
        "            BlurredBackgroundDrawableRenderNode.inu_invalidateLiquidGlassDrawables()\n"
        "        }\n"
        "    }\n"
    )
    if ios_source.count(refresh_call) == 3 and ios_source.count(refresh_method) == 1:
        if (
            ios_source.count("import android.os.Build\n") != 1
            or ios_source.count("import org.telegram.ui.Components.blur3.drawable.BlurredBackgroundDrawableRenderNode\n") != 1
        ):
            raise SystemExit("[ERROR] iOS settings liquid-glass imports changed; refusing to guess.")
        for assignment in (
            "InuConfig.LIQUID_GLASS_ANGLE.value = it.toInt()",
            "InuConfig.LIQUID_GLASS_INTENSITY.value = it.toInt()",
            "InuConfig.LIQUID_GLASS_TINT.value = it.toInt()",
        ):
            if ios_source.count(assignment) != 1:
                raise SystemExit("[ERROR] iOS settings slider behavior changed; refusing to alter it.")
        ios_source = ios_source.replace(refresh_call, "", 3)
        ios_source = ios_source.replace(refresh_method, "", 1)
        ios_source = ios_source.replace("import android.os.Build\n", "", 1)
        ios_source = ios_source.replace(
            "import org.telegram.ui.Components.blur3.drawable.BlurredBackgroundDrawableRenderNode\n",
            "",
            1,
        )
        ios.write_text(ios_source, encoding="utf-8")
        print("[OK] iOS settings no longer call the refresh method from the excluded liquid-glass patch.")
    elif (
        "refreshLiquidGlassEffects()" not in ios_source
        and "inu_invalidateLiquidGlassDrawables" not in ios_source
        and "import android.os.Build\n" not in ios_source
        and "import org.telegram.ui.Components.blur3.drawable.BlurredBackgroundDrawableRenderNode\n" not in ios_source
        and all(
            ios_source.count(assignment) == 1
            for assignment in (
                "InuConfig.LIQUID_GLASS_ANGLE.value = it.toInt()",
                "InuConfig.LIQUID_GLASS_INTENSITY.value = it.toInt()",
                "InuConfig.LIQUID_GLASS_TINT.value = it.toInt()",
            )
        )
    ):
        print("[OK] iOS settings refresh dependency already removed; slider settings remain enabled.")
    else:
        raise SystemExit("[ERROR] iOS settings liquid-glass dependency is in an unknown state.")

    blur_patch = repo / "patches" / "entiny" / "chat" / "chat-blur-resume-settle.patch"
    if not blur_patch.is_file():
        raise SystemExit("[ERROR] Chat blur resume patch is missing.")
    patch_lines = blur_patch.read_text(encoding="utf-8").splitlines(keepends=True)
    stale_call = (
        "+                    org.telegram.ui.Components.blur3.drawable."
        "BlurredBackgroundDrawableRenderNode.inu_invalidateLiquidGlassDrawables();"
    )
    stale_indices = [i for i, line in enumerate(patch_lines) if line.rstrip("\r\n") == stale_call]
    required_blur_additions = (
        "contentView.invalidateBlur();",
        "                checkInsets();",
        "                updatePagedownButtonsPosition();",
        "invalidateMergedVisibleBlurredPositionsAndSources(BLUR_INVALIDATE_FLAG_POSITIONS | BLUR_INVALIDATE_FLAG_CLIP);",
        "invalidateAllGlassAttachedViews();",
    )
    if stale_indices:
        if len(stale_indices) != 1:
            raise SystemExit("[ERROR] Chat blur patch has an ambiguous excluded liquid-glass reference.")
        stale_index = stale_indices[0]
        hunk_start = max((i for i in range(stale_index) if patch_lines[i].startswith("@@ -")), default=-1)
        if hunk_start < 0:
            raise SystemExit("[ERROR] Chat blur patch hunk header is missing.")
        header_match = re.match(
            r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$",
            patch_lines[hunk_start].rstrip("\r\n"),
        )
        if not header_match:
            raise SystemExit("[ERROR] Chat blur patch hunk header is invalid.")
        del patch_lines[stale_index]
        hunk_end = next(
            (i for i in range(hunk_start + 1, len(patch_lines))
             if patch_lines[i].startswith("@@ -") or patch_lines[i].startswith("diff --git ")),
            len(patch_lines),
        )
        body = patch_lines[hunk_start + 1:hunk_end]
        old_count = sum(line.startswith((" ", "-")) for line in body)
        new_count = sum(line.startswith((" ", "+")) for line in body)
        patch_lines[hunk_start] = (
            f"@@ -{header_match.group(1)},{old_count} +{header_match.group(3)},{new_count} @@"
            f"{header_match.group(5)}\n"
        )

        separator = next((i for i, line in enumerate(patch_lines) if line.rstrip("\r\n") == "---"), -1)
        first_diff = next((i for i, line in enumerate(patch_lines) if line.startswith("diff --git ")), -1)
        if separator < 0 or first_diff < 0 or separator >= first_diff:
            raise SystemExit("[ERROR] Chat blur patch summary header is malformed.")
        stats = patch_lines[separator + 1:first_diff]
        row_matches = [i for i, line in enumerate(stats) if "ChatActivity.java" in line and "|" in line]
        summary_matches = [i for i, line in enumerate(stats) if re.search(r"\d+ files? changed", line)]
        if len(row_matches) != 1 or len(summary_matches) != 1:
            raise SystemExit("[ERROR] Chat blur patch summary rows are ambiguous.")
        row = stats[row_matches[0]].rstrip("\r\n")
        row_match = re.match(r"^(\s*.*?\|\s*)(\d+)(\s+.*)$", row)
        if not row_match or int(row_match.group(2)) < 1:
            raise SystemExit("[ERROR] Chat blur patch file summary is invalid.")
        stats[row_matches[0]] = f"{row_match.group(1)}{int(row_match.group(2)) - 1}{row_match.group(3)}\n"
        summary = stats[summary_matches[0]].rstrip("\r\n")
        summary_match = re.match(
            r"^(\s*)(\d+) files? changed, (\d+) insertions\(\+\)"
            r"(?:, (\d+) deletions\(-\))?$",
            summary,
        )
        if not summary_match or int(summary_match.group(3)) < 1:
            raise SystemExit("[ERROR] Chat blur patch totals are invalid.")
        stats[summary_matches[0]] = (
            f"{summary_match.group(1)}{summary_match.group(2)} file"
            f"{'s' if int(summary_match.group(2)) != 1 else ''} changed, "
            f"{int(summary_match.group(3)) - 1} insertions(+)"
            f"{', ' + summary_match.group(4) + ' deletions(-)' if summary_match.group(4) is not None else ''}\n"
        )
        patch_lines = patch_lines[:separator + 1] + stats + patch_lines[first_diff:]
        blur_patch.write_text("".join(patch_lines), encoding="utf-8")
        print("[OK] Chat blur resume patch no longer references the excluded liquid-glass helper.")
    elif not any("inu_invalidateLiquidGlassDrawables" in line for line in patch_lines):
        print("[OK] Chat blur resume patch already adapted for the excluded liquid-glass helper.")
    else:
        raise SystemExit("[ERROR] Chat blur patch has an unknown excluded-helper state.")

    adapted_patch = blur_patch.read_text(encoding="utf-8")
    if "inu_invalidateLiquidGlassDrawables" in adapted_patch:
        raise SystemExit("[ERROR] Excluded liquid-glass helper remains in the active chat blur patch.")
    for addition in required_blur_additions:
        if addition not in adapted_patch:
            raise SystemExit("[ERROR] Chat blur resume behavior was lost: " + addition.strip())

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
    adapt_premium_badge_patch(repo)
    adapt_archive_media_patch(repo)
    adapt_ios_input_bar_patch(repo)
    adapt_burn_voice_round_patch(repo)
    adapt_feed_chatactivity_patch(repo)
    adapt_input_menu_reserve_patch(repo)
    adapt_local_names_patch(repo)
    adapt_system_folders_patch(repo)
    adapt_private_reply_multiline_patch(repo)
    adapt_hide_business_bot_banner_patch(repo)
    adapt_excluded_helper_references(repo)

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
