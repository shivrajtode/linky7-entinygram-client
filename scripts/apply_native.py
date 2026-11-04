#!/usr/bin/env python3
"""Apply Linky7 native app identity, Studio Activity, custom icon and Telegram API credentials."""
from __future__ import annotations
import argparse
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ANDROID = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID)


def replace_string_values(res_root: Path) -> None:
    replacements = {
        "AppName": "Linky7",
        "AppNameBeta": "Linky7 Beta",
        "Page1Title": "Linky7",
        "AppUpdate": "Update Linky7",
        "AppUpdateBeta": "Update Linky7 Beta",
    }
    touched = 0
    for path in res_root.glob("values*/strings.xml"):
        text = path.read_text(encoding="utf-8")
        before = text
        for name, value in replacements.items():
            pattern = rf'(<string\s+name="{re.escape(name)}"[^>]*>).*?(</string>)'
            text = re.sub(pattern, lambda m, v=value: m.group(1) + v + m.group(2), text, flags=re.S)
        if text != before:
            path.write_text(text, encoding="utf-8")
            touched += 1
    if touched == 0:
        raise RuntimeError("No AppName string resources were updated; upstream resource layout changed.")


def patch_manifest(manifest: Path) -> None:
    if not manifest.is_file():
        raise RuntimeError(f"Android manifest missing: {manifest}")
    tree = ET.parse(manifest)
    root = tree.getroot()
    app = root.find("application")
    if app is None:
        raise RuntimeError("Android manifest has no <application> element.")
    app.set(f"{{{ANDROID}}}icon", "@mipmap/ic_linky7")
    app.set(f"{{{ANDROID}}}roundIcon", "@mipmap/ic_linky7")
    # The main app's default launcher alias otherwise overrides android:icon.
    for child in app:
        if child.tag in ("activity-alias",) and child.get(f"{{{ANDROID}}}name", "").endswith("DefaultIcon"):
            child.set(f"{{{ANDROID}}}icon", "@mipmap/ic_linky7")

    class_name = "desu.inugram.linky7.Linky7StudioActivity"
    for child in list(app):
        if child.tag == "activity" and child.get(f"{{{ANDROID}}}name") == class_name:
            app.remove(child)
    activity = ET.SubElement(app, "activity", {
        f"{{{ANDROID}}}name": class_name,
        f"{{{ANDROID}}}label": "Linky7 Studio",
        f"{{{ANDROID}}}icon": "@mipmap/ic_linky7_studio",
        f"{{{ANDROID}}}exported": "true",
        f"{{{ANDROID}}}theme": "@style/Theme.TMessages",
        f"{{{ANDROID}}}windowSoftInputMode": "adjustResize",
    })
    intent = ET.SubElement(activity, "intent-filter")
    ET.SubElement(intent, "action", {f"{{{ANDROID}}}name": "android.intent.action.MAIN"})
    ET.SubElement(intent, "category", {f"{{{ANDROID}}}name": "android.intent.category.LAUNCHER"})

    internet = "android.permission.INTERNET"
    if not any(x.tag == "uses-permission" and x.get(f"{{{ANDROID}}}name") == internet for x in root):
        ET.SubElement(root, "uses-permission", {f"{{{ANDROID}}}name": internet})
    ET.indent(tree, space="    ")
    tree.write(manifest, encoding="utf-8", xml_declaration=True)


def patch_buildvars(path: Path, api_id: str, api_hash: str) -> None:
    if not re.fullmatch(r"[1-9][0-9]{5,11}", api_id):
        raise RuntimeError("Telegram API ID must be a numeric value copied from my.telegram.org/apps.")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        raise RuntimeError("Telegram API hash must be exactly 32 hexadecimal characters.")
    if not path.is_file():
        raise RuntimeError(f"BuildVars.java missing: {path}")
    text = path.read_text(encoding="utf-8")
    text, id_count = re.subn(r"(public\s+static\s+(?:final\s+)?int\s+APP_ID\s*=\s*)\d+(\s*;)", rf"\g<1>{api_id}\g<2>", text, count=1)
    text, hash_count = re.subn(r'(public\s+static\s+String\s+APP_HASH\s*=\s*)"[0-9a-fA-F]+"(\s*;)', lambda m: m.group(1) + '"' + api_hash + '"' + m.group(2), text, count=1)
    if id_count != 1 or hash_count != 1:
        raise RuntimeError("Could not safely replace APP_ID/APP_HASH in BuildVars.java; refusing to build with shared/default credentials.")
    # These are official Telegram-owned integration credentials/features. A fork using
    # its own API_ID/API_HASH must not claim official passkey or Google SafetyNet support.
    text, passkey_count = re.subn(r"(public\s+static\s+(?:final\s+)?boolean\s+SUPPORTS_PASSKEYS\s*=\s*)true(\s*;)", r"\g<1>false\g<2>", text, count=1)
    if passkey_count == 0 and not re.search(r"SUPPORTS_PASSKEYS\s*=\s*false", text):
        raise RuntimeError("Could not safely disable official-only passkey support in BuildVars.java.")
    # These optional official integration values may be absent in a future upstream tag.
    text, _ = re.subn(r'(public\s+static\s+(?:final\s+)?String\s+SAFETYNET_KEY\s*=\s*)"[^"]*"(\s*;)', r'\g<1>""\g<2>', text, count=1)
    text, _ = re.subn(r'(public\s+static\s+(?:final\s+)?String\s+GOOGLE_AUTH_CLIENT_ID\s*=\s*)"[^"]*"(\s*;)', r'\g<1>""\g<2>', text, count=1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--builder", required=True, type=Path)
    parser.add_argument("--api-id", required=True)
    parser.add_argument("--api-hash", required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    builder = args.builder.resolve()
    worktree = repo / "worktree-pluginless"
    main_project = worktree / "TMessagesProj"
    app_project = worktree / "TMessagesProj_App"
    if not (main_project / "src/main/AndroidManifest.xml").is_file():
        raise RuntimeError("Pinned Telegram Android manifest was not found in worktree-pluginless.")

    # The upstream app id is deliberately retained to preserve EntinyGram's matching
    # Firebase/push project and account authorities. The installed display name is Linky7.
    patch_buildvars(main_project / "src/main/java/org/telegram/messenger/BuildVars.java", args.api_id.strip(), args.api_hash.strip())
    replace_string_values(main_project / "src/main/res")
    patch_manifest(main_project / "src/main/AndroidManifest.xml")

    res_src = builder / "overlay" / "res"
    res_dest = main_project / "src/main/res"
    for folder in res_src.iterdir():
        if folder.is_dir():
            target = res_dest / folder.name
            target.mkdir(parents=True, exist_ok=True)
            for file in folder.iterdir():
                shutil.copy2(file, target / file.name)
        elif folder.is_file():
            shutil.copy2(folder, res_dest / folder.name)

    # Place the native Activity directly in the pluginless Android app module.
    # Android Gradle's Kotlin plugin compiles Kotlin sources in Java source roots too.
    kotlin_file = app_project / "src/main/java/desu/inugram/linky7/Linky7StudioActivity.kt"
    kotlin_file.parent.mkdir(parents=True, exist_ok=True)
    source_activity = builder / "overlay" / "src" / "fork-app" / "linky7" / "Linky7StudioActivity.kt"
    if not source_activity.is_file():
        raise RuntimeError(f"Native Linky7 Kotlin Activity is missing: {source_activity}")
    shutil.copy2(source_activity, kotlin_file)
    if not kotlin_file.is_file() or kotlin_file.stat().st_size < 10000:
        raise RuntimeError("Native Linky7 Kotlin Activity copy failed or is incomplete.")

    print("[OK] Linky7 app label and launcher icon applied.")
    print("[OK] Native Linky7 Studio Activity registered as a second launcher entry (not a plugin).")
    print("[OK] User-owned Telegram API credentials injected (APP_HASH redacted).")
    print("[OK] OpenAI and Bot API keys remain runtime settings; they are not embedded in this APK.")
    print("[INFO] Existing EntinyGram applicationId retained for push/account compatibility; uninstall an older differently signed copy before installing this debug APK.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
