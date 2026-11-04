package desu.inugram.linky7

import android.app.Activity
import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.ArrayAdapter
import android.widget.TextView
import android.widget.Toast
import android.graphics.Color
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.concurrent.Executors
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64

/** Native Linky7 post studio bundled inside the EntinyGram/Telegram APK. */
class Linky7StudioActivity : Activity() {
    private val worker = Executors.newSingleThreadExecutor()
    private lateinit var vault: Linky7Vault
    private lateinit var postScroll: ScrollView
    private lateinit var imageScroll: ScrollView
    private lateinit var status: TextView
    private lateinit var botTokenField: EditText
    private lateinit var chatIdField: EditText
    private lateinit var openAiKeyField: EditText
    private lateinit var sourceField: EditText
    private lateinit var briefField: EditText
    private lateinit var languageField: EditText
    private lateinit var codeField: EditText
    private lateinit var jsonField: EditText
    private lateinit var previewText: TextView
    private lateinit var imagePromptField: EditText
    private lateinit var imageView: ImageView
    private lateinit var templateSpinner: Spinner
    private lateinit var textModelSpinner: Spinner
    private lateinit var modelSpinner: Spinner
    private lateinit var attachImageCheck: CheckBox
    private var selectedImageUri: Uri? = null
    private var latestImage: File? = null
    private val templateNames = arrayOf(
        "1 · GitHub project showcase",
        "2 · Android app release",
        "3 · Website / SaaS launch",
        "4 · Tool / utility spotlight",
        "5 · Tutorial / step-by-step",
        "6 · Changelog / update",
        "7 · News / research post",
        "8 · 2026 Rich Code Post"
    )
    private val allowedBlockTypes = setOf(
        "paragraph", "heading", "pre", "footer", "divider", "mathematical_expression",
        "anchor", "list", "blockquote", "expandable_blockquote", "pullquote",
        "table", "details", "buttons"
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        vault = Linky7Vault(this)
        latestImage = vault.get("last_image")?.takeIf { it.isNotBlank() }?.let(::File)?.takeIf { it.isFile }
        buildScreen()
    }

    override fun onDestroy() {
        worker.shutdownNow()
        super.onDestroy()
    }

    private fun d(value: Int): Int = (value * resources.displayMetrics.density + 0.5f).toInt()

    private fun buildScreen() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(13, 17, 28))
            setPadding(d(14), d(12), d(14), d(12))
        }
        val header = TextView(this).apply {
            text = "LINKY7 STUDIO\nAutomated Telegram Rich Messages · 2026"
            setTextColor(Color.WHITE)
            textSize = 21f
            setPadding(d(4), d(10), d(4), d(14))
            gravity = Gravity.CENTER_VERTICAL
        }
        root.addView(header, LinearLayout.LayoutParams(-1, -2))
        val tabs = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val postTab = Button(this).apply { text = "Rich Post Studio"; isAllCaps = false }
        val imageTab = Button(this).apply { text = "Separate AI Image Lab"; isAllCaps = false }
        tabs.addView(postTab, LinearLayout.LayoutParams(0, d(48), 1f))
        tabs.addView(imageTab, LinearLayout.LayoutParams(0, d(48), 1f))
        root.addView(tabs)
        status = TextView(this).apply {
            text = "Ready · Telegram login is handled by the native client. Bot publishing uses a separate bot token."
            setTextColor(Color.rgb(150, 213, 205)); textSize = 12f
            setPadding(d(5), d(8), d(5), d(8))
        }
        root.addView(status, LinearLayout.LayoutParams(-1, -2))

        postScroll = ScrollView(this)
        imageScroll = ScrollView(this)
        postScroll.addView(buildPostPage())
        imageScroll.addView(buildImagePage())
        root.addView(postScroll, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(imageScroll, LinearLayout.LayoutParams(-1, 0, 1f))
        imageScroll.visibility = View.GONE
        postTab.setOnClickListener { postScroll.visibility = View.VISIBLE; imageScroll.visibility = View.GONE }
        imageTab.setOnClickListener { saveConfig(); postScroll.visibility = View.GONE; imageScroll.visibility = View.VISIBLE }
        setContentView(root)
    }

    private fun pageColumn(): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(d(2), d(8), d(2), d(22))
    }

    private fun label(text: String): TextView = TextView(this).apply {
        this.text = text; setTextColor(Color.rgb(219, 226, 242)); textSize = 14f
        setPadding(d(3), d(10), d(3), d(4))
    }

    private fun input(hint: String, multiline: Boolean = false, secret: Boolean = false): EditText = EditText(this).apply {
        this.hint = hint
        setTextColor(Color.WHITE); setHintTextColor(Color.rgb(135, 145, 166))
        textSize = 14f
        setPadding(d(12), d(9), d(12), d(9))
        setBackgroundColor(Color.rgb(29, 37, 54))
        inputType = if (secret) InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            else if (multiline) InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            else InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        minLines = if (multiline) 3 else 1
        maxLines = if (multiline) 8 else 1
        gravity = if (multiline) Gravity.TOP else Gravity.CENTER_VERTICAL
    }

    private fun addInput(parent: LinearLayout, name: String, view: EditText, minHeight: Int = 0) {
        parent.addView(label(name))
        parent.addView(view, LinearLayout.LayoutParams(-1, if (minHeight > 0) d(minHeight) else -2).apply {
            bottomMargin = d(5)
        })
    }

    private fun action(parent: LinearLayout, text: String, click: () -> Unit): Button {
        val b = Button(this).apply { this.text = text; isAllCaps = false; setOnClickListener { click() } }
        parent.addView(b, LinearLayout.LayoutParams(-1, d(48)).apply { topMargin = d(5); bottomMargin = d(4) })
        return b
    }

    private fun buildPostPage(): View {
        val page = pageColumn()
        page.addView(label("Connection settings · Saved encrypted on this device"))
        openAiKeyField = input("OpenAI API key (sk-…)", secret = true).apply { setText(vault.get("openai_key").orEmpty()) }
        botTokenField = input("Telegram bot token from @BotFather", secret = true).apply { setText(vault.get("bot_token").orEmpty()) }
        chatIdField = input("Private chat ID (numeric, e.g. 123456789)").apply { setText(vault.get("chat_id").orEmpty()) }
        addInput(page, "OpenAI API key · GPT-6 text + GPT-Image", openAiKeyField)
        addInput(page, "Bot token · separate from your phone-number Telegram login", botTokenField)
        addInput(page, "Destination chat ID", chatIdField)
        action(page, "Save encrypted settings") { saveConfig(); toast("Settings saved securely") }
        action(page, "Verify bot and private chat") { saveConfig(); verifyTarget() }
        action(page, "Find my private chat ID from the bot updates") { saveConfig(); discoverPrivateTarget() }

        page.addView(label("Automatic post builder"))
        page.addView(label("Text AI model · no Gemini"))
        textModelSpinner = Spinner(this)
        textModelSpinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item,
            arrayOf("GPT-6.1 Terra · balanced quality", "GPT-6 Luna · lower cost"))
        page.addView(textModelSpinner, LinearLayout.LayoutParams(-1, d(48)))
        templateSpinner = Spinner(this)
        templateSpinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, templateNames)
        templateSpinner.setSelection(7)
        page.addView(templateSpinner, LinearLayout.LayoutParams(-1, d(48)))
        sourceField = input("Optional source URL · GitHub repository or website")
        briefField = input("Describe the topic, project, release or post idea…", multiline = true)
        languageField = input("Code language (default Kotlin)").apply { setText("Kotlin") }
        codeField = input("Optional code / source snippet. Leave blank for AI-generated example.", multiline = true)
        addInput(page, "Source URL (automatic research context)", sourceField)
        addInput(page, "Your brief / topic / project details", briefField, 112)
        addInput(page, "Code language for template 8", languageField)
        addInput(page, "Optional code sample", codeField, 104)
        action(page, "GENERATE COMPLETE 2026 RICH POST") { saveConfig(); generatePost() }

        page.addView(label("Generated Rich Message JSON · editable before publishing"))
        jsonField = input("AI-generated rich_message JSON will appear here…", multiline = true).apply { minLines = 10; maxLines = 24 }
        page.addView(jsonField, LinearLayout.LayoutParams(-1, d(250)))
        action(page, "PREVIEW FORMATTED POST") {
            try { previewText.text = renderPreview(JSONObject(jsonField.text.toString())) }
            catch (e: Exception) { toast("Preview error: ${e.message}") }
        }
        previewText = TextView(this).apply {
            setTextColor(Color.WHITE); textSize = 14f; isTextSelectable = true
            setPadding(d(12), d(12), d(12), d(12)); setBackgroundColor(Color.rgb(25, 33, 49))
            text = "Formatted rich-post preview appears here."
        }
        page.addView(previewText, LinearLayout.LayoutParams(-1, -2).apply { topMargin = d(6); bottomMargin = d(8) })
        attachImageCheck = CheckBox(this).apply {
            text = "Attach the latest AI image as the hero photo"
            setTextColor(Color.WHITE)
            isChecked = true
        }
        page.addView(attachImageCheck)
        action(page, "PUBLISH RICH MESSAGE TO PRIVATE CHAT") { saveConfig(); publishRichPost() }
        action(page, "Clear generated draft") { jsonField.setText(""); previewText.text = "Formatted rich-post preview appears here."; setStatus("Draft cleared") }
        addCredits(page)
        return page
    }

    private fun buildImagePage(): View {
        val page = pageColumn()
        page.addView(label("Independent image AI · Gemini is not used"))
        modelSpinner = Spinner(this)
        modelSpinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item,
            arrayOf("GPT-Image-2.5 Sunburst · best editing precision", "GPT-Image-2.5 Flare · faster generation"))
        page.addView(modelSpinner, LinearLayout.LayoutParams(-1, d(48)))
        imagePromptField = input("Describe the image. For realistic photography: natural skin texture, true lens optics, believable lighting and physical detail…", multiline = true)
        addInput(page, "Image prompt / natural photo-editing instructions", imagePromptField, 126)
        action(page, "Choose an existing photo to edit") {
            val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE); type = "image/*"
            }
            startActivityForResult(intent, REQUEST_IMAGE)
        }
        action(page, "GENERATE / EDIT HIGH-REALISM IMAGE") { saveConfig(); generateImage() }
        imageView = ImageView(this).apply { adjustViewBounds = true; scaleType = ImageView.ScaleType.FIT_CENTER }
        page.addView(imageView, LinearLayout.LayoutParams(-1, d(250)))
        latestImage?.let { showImage(it) }
        action(page, "Use this image in the next Rich Post") {
            latestImage?.let {
                vault.put("last_image", it.absolutePath)
                setStatus("Image attached to the next Rich Post")
                toast("Image ready for Rich Post")
            } ?: toast("Generate an image first")
        }
        page.addView(label("Realism note: image generation can produce artifacts; inspect the result before publishing."))
        addCredits(page)
        return page
    }

    private fun addCredits(page: LinearLayout) {
        page.addView(label("Made by Shivraj"))
        page.addView(label("GitHub: https://github.com/shivrajtode\nTelegram: https://t.me/Shivraj_editx\n\nBased on EntinyGram / Inugram and Telegram Android. See THIRD_PARTY_NOTICES.md and retained upstream licence files for the complete acknowledgements and terms."))
    }

    private fun saveConfig() {
        if (::openAiKeyField.isInitialized) vault.put("openai_key", openAiKeyField.text.toString().trim())
        if (::botTokenField.isInitialized) vault.put("bot_token", botTokenField.text.toString().trim())
        if (::chatIdField.isInitialized) vault.put("chat_id", chatIdField.text.toString().trim())
    }

    private fun token(): String = vault.get("bot_token").orEmpty().also { require(it.isNotBlank()) { "Enter your BotFather token and save settings." } }
    private fun openAiKey(): String = vault.get("openai_key").orEmpty().also { require(it.isNotBlank()) { "Enter an OpenAI API key and save settings." } }

    private fun setStatus(message: String) { runOnUiThread { status.text = message } }
    private fun toast(message: String) { Toast.makeText(this, message, Toast.LENGTH_LONG).show() }

    private fun onWorker(task: () -> String, after: (String) -> Unit) {
        setStatus("Working… keep the app open until the request finishes.")
        worker.execute {
            val result = try { task() } catch (e: Exception) { "ERROR: ${e.message ?: e.javaClass.simpleName}" }
            runOnUiThread { setStatus(result); after(result) }
        }
    }

    private fun verifyTarget() {
        val chatId = chatIdField.text.toString().trim()
        onWorker({
            require(chatId.isNotBlank()) { "Enter the private chat ID." }
            val botToken = token()
            val me = telegramCall(botToken, "getMe", JSONObject())
            val chat = telegramCall(botToken, "getChat", JSONObject().put("chat_id", chatId))
            require(chat.optString("type") == "private") { "The destination is not a private chat. Use your numeric private chat ID." }
            "Bot verified: @${me.optString("username")} · private chat ID: ${chat.optString("id")}"
        }) { if (!it.startsWith("ERROR:")) toast("Bot and private chat verified") }
    }

    private fun discoverPrivateTarget() {
        onWorker({
            val updates = telegramUpdates(token())
            var foundId = ""
            for (i in updates.length() - 1 downTo 0) {
                val update = updates.optJSONObject(i) ?: continue
                val message = update.optJSONObject("message") ?: update.optJSONObject("edited_message") ?: continue
                val chat = message.optJSONObject("chat") ?: continue
                if (chat.optString("type") == "private") {
                    foundId = chat.optLong("id").toString()
                    break
                }
            }
            require(foundId.isNotBlank()) { "No private bot update found. Open your bot in Telegram, press Start, send a message, then retry. If the bot uses a webhook, enter the ID manually or disable the webhook first." }
            foundId
        }) { id ->
            if (!id.startsWith("ERROR:")) {
                chatIdField.setText(id)
                saveConfig()
                toast("Private chat ID found and saved")
            }
        }
    }

    private fun generatePost() {
        val brief = briefField.text.toString().trim()
        val source = sourceField.text.toString().trim()
        val template = templateSpinner.selectedItemPosition + 1
        val language = languageField.text.toString().trim().ifBlank { "Kotlin" }
        val code = codeField.text.toString().trim()
        onWorker({
            require(brief.isNotBlank() || source.isNotBlank()) { "Enter a topic/brief or a source URL." }
            val sourceContext = if (source.isNotBlank()) inspectSource(source) else "No external source supplied. Do not invent factual claims."
            val prompt = buildPostPrompt(template, brief, source, sourceContext, language, code)
            val model = if (textModelSpinner.selectedItemPosition == 1) "gpt-6-luna" else "gpt-6.1-terra"
            val raw = openAiResponses(openAiKey(), prompt, model)
            val clean = raw.trim().removePrefix("```json").removePrefix("```").removeSuffix("```").trim()
            val start = clean.indexOf('{'); val end = clean.lastIndexOf('}')
            require(start >= 0 && end > start) { "AI response was not a JSON object. Try Generate again." }
            val obj = JSONObject(clean.substring(start, end + 1))
            validateDraft(obj)
            obj.toString(2)
        }) { output -> if (!output.startsWith("ERROR:")) {
            jsonField.setText(output)
            try { previewText.text = renderPreview(JSONObject(output)) } catch (_: Exception) { }
            toast("Complete Rich Message draft generated")
        } }
    }

    private fun renderPreview(draft: JSONObject): String {
        val out = StringBuilder()
        out.append(draft.optString("title")).append("\n\n")
        fun appendBlocks(blocks: JSONArray?, indent: String = "") {
            if (blocks == null) return
            for (i in 0 until blocks.length()) {
                val b = blocks.optJSONObject(i) ?: continue
                when (b.optString("type")) {
                    "heading" -> out.append(indent).append("# ").append(b.optString("text")).append("\n\n")
                    "paragraph" -> out.append(indent).append(b.optString("text")).append("\n\n")
                    "pre" -> out.append(indent).append("```").append(b.optString("language")).append("\n")
                        .append(b.optString("text")).append("\n```\n\n")
                    "footer" -> out.append(indent).append("— ").append(b.optString("text")).append("\n\n")
                    "divider" -> out.append(indent).append("────────────────\n\n")
                    "pullquote", "expandable_blockquote" -> out.append(indent).append("❝ ").append(b.optString("text")).append(" ❞\n\n")
                    "blockquote" -> { out.append(indent).append("│ Quote\n"); appendBlocks(b.optJSONArray("blocks"), indent + "  ") }
                    "details" -> { out.append(indent).append("▸ ").append(b.optString("summary")).append("\n"); appendBlocks(b.optJSONArray("blocks"), indent + "  ") }
                    "list" -> {
                        val items = b.optJSONArray("items") ?: JSONArray()
                        for (j in 0 until items.length()) {
                            val item = items.optJSONObject(j) ?: continue
                            out.append(indent).append("• ")
                            val inner = item.optJSONArray("blocks")
                            val first = inner?.optJSONObject(0)
                            out.append(first?.optString("text").orEmpty()).append("\n")
                            if (inner != null && inner.length() > 1) appendBlocks(JSONArray().apply { for (k in 1 until inner.length()) put(inner.get(k)) }, indent + "  ")
                        }
                        out.append("\n")
                    }
                    "buttons" -> {
                        val buttons = b.optJSONArray("buttons") ?: JSONArray()
                        for (j in 0 until buttons.length()) {
                            val button = buttons.optJSONObject(j) ?: continue
                            out.append(indent).append("[ ").append(button.optString("text")).append(" ] ")
                                .append(button.optString("url")).append("\n")
                        }
                        out.append("\n")
                    }
                    "mathematical_expression" -> out.append(indent).append("$ ").append(b.optString("expression")).append(" $\n\n")
                    "anchor" -> out.append(indent).append("⚓ ").append(b.optString("name")).append("\n\n")
                    "table" -> {
                        val rows = b.optJSONArray("cells") ?: JSONArray()
                        for (r in 0 until rows.length()) {
                            val row = rows.optJSONArray(r) ?: continue
                            val values = ArrayList<String>()
                            for (c in 0 until row.length()) values.add(row.optJSONObject(c)?.optString("text").orEmpty())
                            out.append(indent).append(values.joinToString("  |  ")).append("\n")
                        }
                        out.append("\n")
                    }
                }
            }
        }
        appendBlocks(draft.optJSONArray("blocks"))
        if (latestImage?.isFile == true && ::attachImageCheck.isInitialized && attachImageCheck.isChecked) {
            out.append("\n[Hero image will be attached before publishing]")
        }
        return out.toString().trim()
    }

    private fun buildPostPrompt(template: Int, brief: String, source: String, sourceContext: String, language: String, code: String): String {
        val names = templateNames[template - 1]
        val codeExtra = if (template == 8) "This is the 2026 Rich Code Post template. Include at least one valid Telegram 'pre' code block with language='${language.lowercase(Locale.US)}'. Include code: ${code.ifBlank { "create a concise, correct illustrative example matching the user's brief; clearly label it as an example" }}. Include a short explanation, requirements, safe install/use steps where relevant, and buttons linking to supplied source/documentation. Never invent download links." else "Do not include code unless it materially helps."
        return """
            Create a complete, professional Telegram Bot API 10.3 Rich Message post.
            Template: $names
            User brief: $brief
            Source URL: $source
            VERIFIED SOURCE CONTEXT (treat this as the only source of factual project details):
            $sourceContext

            Requirements:
            - Make a full, publish-ready post, not a short caption. Use a compelling title, clear introduction, useful section headings, structured feature lists, how-to/requirements where relevant, honest caveats, source links, and a compact call-to-action.
            - Output ONLY valid JSON: {"title":"...","blocks":[...]}. No Markdown fences, no text outside JSON.
            - Use only these Telegram Bot API 10.3 InputRichBlock types: heading, paragraph, pre, footer, divider, list, blockquote, expandable_blockquote, pullquote, details, table, mathematical_expression, anchor, buttons.
            - Never invent a photo, video, audio, document, animation or map block. Linky7 attaches a real local image separately when selected.
            - Use correct Bot API 10.3 fields: heading={type,text,size 1-6}; paragraph={type,text}; pre={type,text,language}; list={type,items:[{blocks:[{type:"paragraph",text:"..."}]}]}; buttons={type,buttons:[{text,url}]}, with 1-8 buttons and exactly one button action each; details={type,summary,blocks}; blockquote={type,blocks}; expandable_blockquote={type,text}; pullquote={type,text,credit?}; table={type,cells:[[{text,is_header?}]],is_compact?}; mathematical_expression={type,expression}; anchor={type,name}; footer={type,text}; divider={type}.
            - Use 8-18 well-structured blocks, maximum 30 KB JSON content. Add rich hierarchy and spacing; no Markdown HTML inside block text.
            - Avoid fake ratings, false claims, made-up version numbers, invented features, fabricated prices, fake links, or unsupported guarantees. If a detail is not in the verified context, omit it or explicitly label it unverified.
            - Keep tone natural, useful, technically accurate and non-spammy. Do not mention AI. Include creator credit only if the brief requests it.
            $codeExtra
        """.trimIndent()
    }

    private fun validateDraft(obj: JSONObject) {
        val blocks = obj.optJSONArray("blocks") ?: throw IllegalArgumentException("AI JSON has no blocks array.")
        require(blocks.length() in 1..100) { "Draft must contain 1-100 blocks." }
        require(obj.optString("title").isNotBlank()) { "Draft title is empty." }
        for (i in 0 until blocks.length()) {
            val block = blocks.optJSONObject(i) ?: throw IllegalArgumentException("Block ${i + 1} is not an object.")
            val type = block.optString("type")
            require(type in allowedBlockTypes) { "Unsupported Rich Message block type: $type" }
            when (type) {
                "heading" -> {
                    require(block.optString("text").isNotBlank()) { "Heading block ${i + 1} has no text." }
                    require(block.optInt("size", 1) in 1..6) { "Heading block ${i + 1} size must be 1-6." }
                }
                "paragraph", "pre", "footer", "pullquote", "expandable_blockquote" ->
                    require(block.optString("text").isNotBlank()) { "$type block ${i + 1} has no text." }
                "mathematical_expression" -> require(block.optString("expression").isNotBlank()) { "Math block ${i + 1} has no expression." }
                "anchor" -> require(block.optString("name").isNotBlank()) { "Anchor block ${i + 1} has no name." }
                "blockquote" -> require((block.optJSONArray("blocks")?.length() ?: 0) > 0) { "$type block ${i + 1} has no nested blocks." }
                "details" -> {
                    require(block.optString("summary").isNotBlank()) { "Details block ${i + 1} has no summary." }
                    require((block.optJSONArray("blocks")?.length() ?: 0) > 0) { "Details block ${i + 1} has no nested blocks." }
                }
                "list" -> {
                    val items = block.optJSONArray("items") ?: throw IllegalArgumentException("List block ${i + 1} has no items array.")
                    require(items.length() in 1..50) { "List block ${i + 1} must have 1-50 items." }
                    for (j in 0 until items.length()) {
                        val item = items.optJSONObject(j) ?: throw IllegalArgumentException("List item ${j + 1} is invalid.")
                        // Normalize a plain-text shorthand into the Bot API 10.3 ListItem.blocks schema.
                        if (item.optJSONArray("blocks") == null) {
                            val text = item.optString("text").trim()
                            require(text.isNotBlank()) { "List item ${j + 1} is empty." }
                            item.put("blocks", JSONArray().put(JSONObject().put("type", "paragraph").put("text", text)))
                            item.remove("text")
                        }
                    }
                }
                "buttons" -> {
                    val buttons = block.optJSONArray("buttons") ?: throw IllegalArgumentException("Buttons block ${i + 1} has no buttons array.")
                    require(buttons.length() in 1..8) { "A buttons row must contain 1-8 buttons." }
                    for (j in 0 until buttons.length()) {
                        val button = buttons.optJSONObject(j) ?: throw IllegalArgumentException("Button ${j + 1} is invalid.")
                        require(button.optString("text").isNotBlank()) { "Button ${j + 1} has no label." }
                        val actionFields = listOf("url", "callback_data", "web_app", "login_url", "switch_inline_query", "switch_inline_query_current_chat", "switch_inline_query_chosen_chat", "copy_text", "disabled")
                        val setActions = actionFields.count { button.has(it) && !button.isNull(it) }
                        require(setActions == 1) { "Button ${j + 1} must have exactly one action (usually url)." }
                        if (button.has("url")) {
                            val link = button.optString("url")
                            require(link.startsWith("https://") || link.startsWith("http://") || link.startsWith("tg://")) { "Button ${j + 1} has an unsupported URL." }
                        }
                    }
                }
                "table" -> require((block.optJSONArray("cells")?.length() ?: 0) > 0) { "Table block ${i + 1} has no cells." }
                "divider" -> Unit
            }
        }
        require(obj.toString().toByteArray(Charsets.UTF_8).size <= 30000) { "Draft exceeds the safe 30 KB size limit." }
    }

    private fun publishRichPost() {
        val chatId = chatIdField.text.toString().trim()
        val image = if (attachImageCheck.isChecked) latestImage?.takeIf { it.isFile && it.length() > 0 } else null
        onWorker({
            require(chatId.isNotBlank()) { "Enter your numeric private chat ID." }
            val draft = JSONObject(jsonField.text.toString())
            validateDraft(draft)
            val blocks = draft.getJSONArray("blocks")
            val title = draft.optString("title").trim()
            val first = blocks.optJSONObject(0)
            val contentBlocks = JSONArray()
            if (first == null || first.optString("type") != "heading" || first.optString("text").trim() != title) {
                contentBlocks.put(JSONObject().put("type", "heading").put("size", 1).put("text", title))
            }
            for (i in 0 until blocks.length()) contentBlocks.put(blocks.get(i))
            val outgoingBlocks = JSONArray()
            if (image != null) {
                val photo = JSONObject().put("type", "photo").put("photo", JSONObject()
                    .put("type", "photo").put("media", "attach://linky7_hero"))
                outgoingBlocks.put(photo)
            }
            for (i in 0 until contentBlocks.length()) outgoingBlocks.put(contentBlocks.get(i))
            val rich = JSONObject().put("blocks", outgoingBlocks)
            val me = telegramCall(token(), "getMe", JSONObject())
            val sent = sendRichMessage(token(), chatId, rich, image)
            val resultChat = sent.optJSONObject("chat")?.optString("id").orEmpty()
            val messageId = sent.optLong("message_id")
            "PUBLISHED ✓ · Bot @${me.optString("username")} · chat ${resultChat.ifBlank { chatId }} · message $messageId"
        }) { if (it.startsWith("PUBLISHED")) toast("Rich Message sent successfully") }
    }

    private fun generateImage() {
        val promptText = imagePromptField.text.toString().trim()
        onWorker({
            require(promptText.isNotBlank()) { "Enter an image prompt first." }
            val key = openAiKey()
            val model = if (modelSpinner.selectedItemPosition == 1) "gpt-image-2.5-flare" else "gpt-image-2.5-sunburst"
            val realism = "Create a high-fidelity, photorealistic image. Preserve believable physical materials, natural lighting, accurate anatomy and proportions, realistic lens optics, fine but natural texture, coherent shadows and reflections. Avoid plastic skin, over-sharpening, artificial HDR, fake bokeh and obvious synthetic artifacts. User's request: $promptText"
            val imageBytes = if (selectedImageUri != null) imageEdit(key, model, realism, selectedImageUri!!) else imageGenerate(key, model, realism)
            val dir = File(getExternalFilesDir(Environment.DIRECTORY_PICTURES), "Linky7").apply { mkdirs() }
            val file = File(dir, "linky7-${System.currentTimeMillis()}.png")
            file.writeBytes(imageBytes)
            vault.put("last_image", file.absolutePath)
            latestImage = file
            selectedImageUri = null
            "IMAGE READY ✓ · ${file.name} · ${(file.length() / 1024)} KB"
        }) {
            if (it.startsWith("IMAGE READY")) {
                latestImage?.let(::showImage)
                toast("Image generated and saved")
            }
        }
    }

    private fun showImage(file: File) {
        try { imageView.setImageBitmap(BitmapFactory.decodeFile(file.absolutePath)) } catch (_: Exception) { }
    }

    @Deprecated("Uses document picker result for Android 8+ compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_IMAGE && resultCode == RESULT_OK) {
            selectedImageUri = data?.data
            setStatus(if (selectedImageUri != null) "Photo selected · Generate/Edit will use this image" else "No photo selected")
        }
    }

    private fun inspectSource(rawUrl: String): String {
        val url = URL(rawUrl.trim())
        require(url.protocol == "https" || url.protocol == "http") { "Only HTTP/HTTPS source URLs are supported." }
        require(url.host.isNotBlank() && !url.host.equals("localhost", true) && !url.host.startsWith("127.")) { "Invalid source host." }
        if (url.host.equals("github.com", true)) {
            val parts = url.path.trim('/').split('/')
            if (parts.size >= 2) {
                val owner = parts[0]; val repo = parts[1].removeSuffix(".git")
                val meta = httpJson("https://api.github.com/repos/$owner/$repo", null)
                val readme = try { httpJson("https://api.github.com/repos/$owner/$repo/readme", null) } catch (_: Exception) { JSONObject() }
                val readmeText = try { String(Base64.decode(readme.optString("content").replace("\n", ""), Base64.DEFAULT), Charsets.UTF_8) } catch (_: Exception) { "" }
                return "GitHub repository: ${meta.optString("full_name")}\nDescription: ${meta.optString("description")}\nLanguage: ${meta.optString("language")}\nDefault branch: ${meta.optString("default_branch")}\nHomepage: ${meta.optString("homepage")}\nLicense: ${meta.optJSONObject("license")?.optString("spdx_id")}\nStars: ${meta.optInt("stargazers_count")}\nTopics: ${meta.optJSONArray("topics") ?: JSONArray()}\nREADME excerpt:\n${readmeText.take(10000)}"
            }
        }
        val html = httpText(rawUrl)
        val plain = html.replace(Regex("(?is)<script[^>]*>.*?</script>|<style[^>]*>.*?</style>"), " ")
            .replace(Regex("(?s)<[^>]+>"), " ").replace("&nbsp;", " ").replace("&amp;", "&")
            .replace(Regex("\\s+"), " ").trim()
        return "Website text excerpt:\n${plain.take(9000)}"
    }

    private fun httpText(rawUrl: String): String {
        val c = (URL(rawUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = 12000; readTimeout = 18000; setRequestProperty("User-Agent", "Linky7Studio/1.0")
        }
        return try {
            val code = c.responseCode
            require(code in 200..299) { "Source URL HTTP $code" }
            c.inputStream.bufferedReader().use { it.readText().take(1_000_000) }
        } finally { c.disconnect() }
    }

    private fun httpJson(rawUrl: String, body: JSONObject?): JSONObject {
        val c = (URL(rawUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = 12000; readTimeout = 18000
            setRequestProperty("User-Agent", "Linky7Studio/1.0")
            setRequestProperty("Accept", "application/vnd.github+json, application/json")
            if (body != null) { requestMethod = "POST"; doOutput = true; setRequestProperty("Content-Type", "application/json") }
        }
        try {
            if (body != null) c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = c.responseCode
            val stream = if (code in 200..299) c.inputStream else c.errorStream
            val text = BufferedReader(InputStreamReader(stream ?: c.inputStream)).use { it.readText() }
            require(code in 200..299) { "HTTP $code: ${text.take(500)}" }
            return JSONObject(text)
        } finally { c.disconnect() }
    }

    private fun openAiResponses(apiKey: String, prompt: String, model: String): String {
        val body = JSONObject()
            .put("model", model)
            .put("reasoning", JSONObject().put("effort", "low"))
            .put("instructions", "You create factual, polished Telegram Bot API 10.3 rich posts. Follow the user's output JSON schema exactly. Never invent unsupported facts or links.")
            .put("input", prompt)
            .put("max_output_tokens", 5000)
        val root = apiPostJson("https://api.openai.com/v1/responses", apiKey, body)
        val output = root.optJSONArray("output") ?: throw IllegalStateException("OpenAI returned no output array.")
        val parts = StringBuilder()
        for (i in 0 until output.length()) {
            val item = output.optJSONObject(i) ?: continue
            val content = item.optJSONArray("content") ?: continue
            for (j in 0 until content.length()) {
                val part = content.optJSONObject(j) ?: continue
                if (part.optString("type") == "output_text") parts.append(part.optString("text"))
            }
        }
        return parts.toString().trim().ifBlank { throw IllegalStateException("OpenAI response was empty. Status: ${root.optString("status")}") }
    }

    private fun apiPostJson(rawUrl: String, apiKey: String, body: JSONObject): JSONObject {
        val c = (URL(rawUrl).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"; connectTimeout = 20000; readTimeout = 120000; doOutput = true
            setRequestProperty("Authorization", "Bearer $apiKey")
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
        }
        try {
            c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = c.responseCode
            val stream = if (code in 200..299) c.inputStream else c.errorStream
            val text = BufferedReader(InputStreamReader(stream ?: c.inputStream)).use { it.readText() }
            if (code !in 200..299) {
                val detail = try { JSONObject(text).optJSONObject("error")?.optString("message") } catch (_: Exception) { null }
                throw IllegalStateException("OpenAI HTTP $code: ${detail ?: text.take(400)}. Check API billing, project limits and model access.")
            }
            return JSONObject(text)
        } finally { c.disconnect() }
    }

    private fun imageGenerate(apiKey: String, model: String, prompt: String): ByteArray {
        val body = JSONObject().put("model", model).put("prompt", prompt)
            .put("quality", "xhigh").put("size", "1536x1024").put("n", 1).put("output_format", "png")
        val root = apiPostJson("https://api.openai.com/v1/images/generations", apiKey, body)
        val b64 = root.optJSONArray("data")?.optJSONObject(0)?.optString("b64_json").orEmpty()
        require(b64.isNotBlank()) { "Image API returned no b64_json image data." }
        return Base64.decode(b64, Base64.DEFAULT)
    }

    private fun imageEdit(apiKey: String, model: String, prompt: String, uri: Uri): ByteArray {
        val temp = File(cacheDir, "linky7-edit-source.png")
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / sample > 2048) sample *= 2
        val options = BitmapFactory.Options().apply { inSampleSize = sample.coerceAtLeast(1) }
        val bitmap = contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) }
            ?: throw IllegalStateException("Could not decode the selected photo.")
        try {
            temp.outputStream().use { bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it) }
        } finally { bitmap.recycle() }
        return try { imageEditMultipart(apiKey, model, prompt, temp) } finally { temp.delete() }
    }

    private fun imageEditMultipart(apiKey: String, model: String, prompt: String, image: File): ByteArray {
        val boundary = "----Linky7Edit${System.currentTimeMillis()}"
        val c = (URL("https://api.openai.com/v1/images/edits").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"; connectTimeout = 20000; readTimeout = 180000; doOutput = true
            setRequestProperty("Authorization", "Bearer $apiKey")
            setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        }
        try {
            c.outputStream.buffered().use { out ->
                fun field(name: String, value: String) {
                    out.write("--$boundary\r\nContent-Disposition: form-data; name=\"$name\"\r\n\r\n$value\r\n".toByteArray())
                }
                field("model", model); field("prompt", prompt); field("quality", "xhigh")
                field("size", "1536x1024"); field("output_format", "png")
                out.write("--$boundary\r\nContent-Disposition: form-data; name=\"image\"; filename=\"source.png\"\r\nContent-Type: image/png\r\n\r\n".toByteArray())
                image.inputStream().use { it.copyTo(out) }; out.write("\r\n--$boundary--\r\n".toByteArray())
            }
            val code = c.responseCode
            val stream = if (code in 200..299) c.inputStream else c.errorStream
            val text = BufferedReader(InputStreamReader(stream ?: c.inputStream)).use { it.readText() }
            if (code !in 200..299) throw IllegalStateException("OpenAI image edit HTTP $code: ${text.take(500)}")
            val b64 = JSONObject(text).optJSONArray("data")?.optJSONObject(0)?.optString("b64_json").orEmpty()
            require(b64.isNotBlank()) { "Image edit returned no image data." }
            return Base64.decode(b64, Base64.DEFAULT)
        } finally { c.disconnect() }
    }

    private fun telegramUpdates(bot: String): JSONArray {
        val body = JSONObject().put("timeout", 0).put("allowed_updates", JSONArray().put("message").put("edited_message"))
        val c = (URL("https://api.telegram.org/bot$bot/getUpdates").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"; connectTimeout = 15000; readTimeout = 30000; doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
        }
        try {
            c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = c.responseCode
            val text = BufferedReader(InputStreamReader(if (code in 200..299) c.inputStream else c.errorStream)).use { it.readText() }
            val json = JSONObject(text)
            if (code !in 200..299 || !json.optBoolean("ok", false)) {
                throw IllegalStateException("Telegram getUpdates failed (${json.optInt("error_code", code)}): ${json.optString("description", text.take(300))}. A bot webhook may be active; in that case enter the private chat ID manually.")
            }
            return json.optJSONArray("result") ?: JSONArray()
        } finally { c.disconnect() }
    }

    private fun telegramCall(bot: String, method: String, body: JSONObject): JSONObject {
        val c = (URL("https://api.telegram.org/bot$bot/$method").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"; connectTimeout = 15000; readTimeout = 30000; doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
        }
        try {
            c.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code = c.responseCode
            val text = BufferedReader(InputStreamReader(if (code in 200..299) c.inputStream else c.errorStream)).use { it.readText() }
            val json = JSONObject(text)
            if (code !in 200..299 || !json.optBoolean("ok", false)) {
                throw IllegalStateException("Telegram $method failed (${json.optInt("error_code", code)}): ${json.optString("description", text.take(400))}. For a private bot chat, send /start to this bot first.")
            }
            return json.getJSONObject("result")
        } finally { c.disconnect() }
    }

    private fun sendRichMessage(bot: String, chatId: String, rich: JSONObject, image: File?): JSONObject {
        val endpoint = "https://api.telegram.org/bot$bot/sendRichMessage"
        if (image == null) return telegramCall(bot, "sendRichMessage", JSONObject().put("chat_id", chatId).put("rich_message", rich))
        val boundary = "----Linky7Rich${System.currentTimeMillis()}"
        val c = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"; connectTimeout = 20000; readTimeout = 60000; doOutput = true
            setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        }
        try {
            c.outputStream.buffered().use { out ->
                fun field(name: String, value: String) {
                    out.write("--$boundary\r\nContent-Disposition: form-data; name=\"$name\"\r\n\r\n$value\r\n".toByteArray())
                }
                field("chat_id", chatId); field("rich_message", rich.toString())
                val ext = image.extension.lowercase(Locale.US).takeIf { it in setOf("png", "jpg", "jpeg", "webp") } ?: "png"
                val mime = if (ext == "jpg" || ext == "jpeg") "image/jpeg" else if (ext == "webp") "image/webp" else "image/png"
                out.write("--$boundary\r\nContent-Disposition: form-data; name=\"linky7_hero\"; filename=\"linky7-hero.$ext\"\r\nContent-Type: $mime\r\n\r\n".toByteArray())
                image.inputStream().use { it.copyTo(out) }
                out.write("\r\n--$boundary--\r\n".toByteArray())
            }
            val code = c.responseCode
            val text = BufferedReader(InputStreamReader(if (code in 200..299) c.inputStream else c.errorStream)).use { it.readText() }
            val json = JSONObject(text)
            if (code !in 200..299 || !json.optBoolean("ok", false)) {
                throw IllegalStateException("Telegram sendRichMessage failed (${json.optInt("error_code", code)}): ${json.optString("description", text.take(400))}. Check bot rights and whether the user started the bot.")
            }
            return json.getJSONObject("result")
        } finally { c.disconnect() }
    }

    companion object { private const val REQUEST_IMAGE = 7107 }
}

/** AES-GCM vault backed by Android Keystore; API keys are not written as plain preferences. */
private class Linky7Vault(context: android.content.Context) {
    private val prefs = context.getSharedPreferences("linky7_secure_v1", android.content.Context.MODE_PRIVATE)
    private val alias = "linky7.studio.aes.v1"
    private fun secretKey(): SecretKey {
        val ks = java.security.KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setRandomizedEncryptionRequired(true).build())
        return generator.generateKey()
    }
    fun put(name: String, value: String) {
        if (value.isBlank()) { prefs.edit().remove(name).apply(); return }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        val payload = cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        prefs.edit().putString(name, Base64.encodeToString(payload, Base64.NO_WRAP)).apply()
    }
    fun get(name: String): String? {
        val raw = prefs.getString(name, null) ?: return null
        return try {
            val payload = Base64.decode(raw, Base64.NO_WRAP)
            val iv = payload.copyOfRange(0, 12); val ciphertext = payload.copyOfRange(12, payload.size)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(128, iv))
            String(cipher.doFinal(ciphertext), Charsets.UTF_8)
        } catch (_: Exception) { null }
    }
}
