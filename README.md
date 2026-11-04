# Linky7 · EntinyGram Native Telegram Client Builder

**This is the native-source builder, not the earlier EntinyGram plugin.** It fetches EntinyGram v13.1.1-202611020, applies the Telegram Android patchset in pluginless mode, adds Linky7's Kotlin Studio Activity to the app source, applies the custom launcher artwork and creates a debug APK.

## What is built

- **Linky7** — the native Telegram Android client based on EntinyGram's patchset. The standard Telegram phone-number, login-code and optional two-step-verification flow remains the account login. Chats, groups, channels, contacts, calls, media, notifications and normal Telegram client features come from the native source.
- **Linky7 Studio** — a native Kotlin Activity compiled into the same APK/package and exposed as a second launcher icon with an edit badge. It has two internal sections (Rich Post Studio and Separate AI Image Lab). It is not a JavaScript plugin, WebView, separate installed APK, or Bot API replacement for the Telegram account.
- **Rich Post Studio** — automated source-aware post generation and editing, with eight templates. Template 8 is **2026 Rich Code Post**; Kotlin is the default code language, with the language editable. It produces Telegram Bot API 10.3 `InputRichMessage.blocks` and sends them using `sendRichMessage`.
- **Separate AI Image Lab** — image generation and source-photo editing with GPT-Image-2.5 Sunburst or Flare. Gemini is not used by Linky7 Studio.
- **Custom Linky7 logo** — generated Linky7 artwork is applied to the app and Studio launcher entries.
- **Credits** — Made by Shivraj, with your GitHub/Telegram links and an in-app acknowledgement. EntinyGram, Inugram and Telegram upstream credits and original licence files are retained.

## Important: how the build works from Termux

The Lenovo tablet is Android ARM64. Google's Android NDK downloads for Linux are host-x86/x86-64 packages, not native Android/Termux ARM64 packages. Root cannot convert Android's host ABI into Linux x86-64. This builder therefore uses Termux only to prepare and trigger a reproducible **GitHub Actions Linux build**, then downloads the finished APK back into `~/storage/downloads/Linky7.apk`. The full Android/NDK compilation runs on the GitHub runner. No `su`, kernel changes, root filesystem edits or bootloader changes are needed.

The build creates or updates a **public** repository named `linky7-entinygram-client` under the active GitHub CLI account. This keeps the builder, Kotlin integration source and licence/credit notices accessible with the distributed APK, and lets the APK be rebuilt. The upstream EntinyGram and Telegram sources are fetched at build time rather than copied into this small ZIP.

## Before running

1. Install GitHub CLI in Termux and authenticate once:

   ```bash
   pkg update -y && pkg install -y gh git jq python
   gh auth login -h github.com -p https -s repo,workflow -w
   gh auth status
   ```

2. Create your own Telegram API application at **https://my.telegram.org/apps**. The builder asks for the numeric `api_id` and 32-character `api_hash`. A third-party Telegram client must use credentials belonging to its developer; do not rely on EntinyGram's shared API credentials. These values are injected into `BuildVars.java` through GitHub Actions secrets. They will also be embedded in the APK, as Telegram client API credentials normally are.

3. Download this ZIP to Android Downloads, extract it, then run `bash build.sh`.

## Termux update command

The target archive is protected; old builder ZIPs are deleted only after the new ZIP has been verified:

```bash
cd ~/storage/downloads || exit 1
ZIP="Linky7-EntinyGram-Termux-Builder-v1.1.zip"
[ -s "$ZIP" ] || { echo "Download $ZIP first"; exit 1; }
unzip -tq "$ZIP" || exit 1
find . -maxdepth 1 -type f \
  -name 'Linky7-EntinyGram-Termux-Builder-v*.zip' \
  ! -name "$ZIP" -delete
rm -rf Linky7-EntinyGram-Termux-Builder
unzip -oq "$ZIP" || exit 1
cd Linky7-EntinyGram-Termux-Builder || exit 1
bash build.sh
```

This command does not delete Android SDK, Gradle or dependency caches. This cloud build does not use your local SDK/Gradle caches at all.

## First run and settings

1. Install `~/storage/downloads/Linky7.apk` on your tablet. If an earlier EntinyGram APK with a different signing certificate is installed, Android may require uninstalling that old build first. Telegram messages are cloud-synced, but reinstalling/clearing app data means signing in again.
2. Open **Linky7**. It uses the native Telegram login screen: phone number → Telegram verification code → two-step verification if enabled. The app keeps a normal Telegram session after successful login; it does not request OTP on every launch. The upstream application ID `ua.entaytion.entinygram` is deliberately retained to preserve EntinyGram's matching Firebase/FCM and account authorities, so this build replaces the EntinyGram package rather than installing side-by-side. If you need to force the first phone/OTP login after installing over an existing session, run this optional one-time root command before opening the app:

   ```bash
   su -c 'pm clear ua.entaytion.entinygram'
   ```

   This clears all local EntinyGram/Linky7 app data and Studio keys; Telegram cloud messages remain in your Telegram account. Use it only when you want to sign in again. If Android reports a signature conflict during installation, uninstall the previous EntinyGram APK first, then install Linky7.
3. Open the **Linky7 Studio** icon. The Telegram account login and Bot API publisher are deliberately separate.
4. Add an OpenAI API key and a Telegram bot token from `@BotFather` in Rich Post Studio. These are saved encrypted with Android Keystore on the device. They are not compile-time GitHub secrets and are not uploaded by this builder.
5. For a private bot chat, open the bot in Telegram, press **Start**, and send it a message. Use **Find my private chat ID** or enter the numeric ID manually, then **Verify bot and private chat**. `getUpdates` discovery can be unavailable if another service is polling the bot or a webhook is configured; manual chat ID entry still works.
6. Choose one of the eight templates, add a topic/brief or a source URL, and tap **Generate Complete 2026 Rich Post**. Review/edit the JSON, then publish. Template 8 generates a code-first post with a Kotlin example by default.
7. In **Separate AI Image Lab**, generate or edit a photo, then select **Use this image in the next Rich Post**. Inspect the result before sending.

## API and billing notes

- Text generation defaults to `gpt-6.1-terra` through the OpenAI Responses API.
- Image generation/editing defaults to `gpt-image-2.5-sunburst` at xhigh quality; Flare is available for faster work.
- ChatGPT subscription access does **not** automatically include API credits. OpenAI API billing/project limits apply. An HTTP 429/quota message usually indicates API account/project limit or billing, not a Gemini failure.
- The Bot API `sendRichMessage` method sends a rich post as the bot. It does not send the rich post as your personal account. The bot can write in its private chat only after the user has started it; a channel/group requires that bot to have the required permissions.
- `sendRichMessage` is part of Telegram Bot API 10.1 and later; Linky7 targets the current 10.3 Rich Message types and button blocks. An outdated Bot API server/client wrapper may not support it; Linky7 calls Telegram's HTTPS Bot API endpoint directly.
- AI-generated factual content must be reviewed. The app fetches GitHub repository metadata/README or a public web page excerpt when a source URL is supplied, but it cannot guarantee that all AI-generated claims are correct.
- Image generation can still produce artifacts; no model can guarantee a completely non-AI appearance.

## EntinyGram patch selection

This is an EntinyGram-based full Telegram client build in pluginless mode. It intentionally excludes patches that defeat recipient privacy/content protection, save self-destructing media or stories, suppress screenshot notifications, alter read/seen behaviour, locally unlock Telegram paid/restricted limits, or introduce EntinyGram Gemini/translator AI screens. The remaining normal client, UI, performance, bug-fix and non-plugin EntinyGram patches are kept. The original upstream `series` is backed up in the CI checkout as `series.linky7-original`; upstream patch files are not deleted.

## Build output and troubleshooting

- APK: `~/storage/downloads/Linky7.apk`
- GitHub source/build repository: `https://github.com/<active-account>/linky7-entinygram-client`
- Build runs and logs: repository → Actions → **Build Linky7 Telegram Client** (ARM64 `assembleAfatDebug` variant).
- If a run fails, share its public Actions run URL or only the failed task/error tail. Never paste your OpenAI API key, bot token, Telegram API hash, or GitHub token.

v1.1 uses EntinyGram’s documented `bun run setup` and pluginless `TMessagesProj_App:assembleDebug` task. It also copies the native Kotlin Activity directly into the pluginless app module before compilation. This ZIP has shell/Python syntax and static structure checks only. A complete Android APK build can be confirmed only by the GitHub Actions run on the actual upstream source and Android toolchain.
