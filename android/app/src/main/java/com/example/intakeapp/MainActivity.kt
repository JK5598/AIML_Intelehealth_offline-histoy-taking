package com.example.intakeapp

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
//----- Lia's code: imports for the styled lines and the option buttons -----
import android.graphics.Color
import android.graphics.Typeface
import android.text.SpannableString
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.text.InputType
import android.widget.PopupMenu
import androidx.appcompat.app.AlertDialog
import android.widget.LinearLayout
import org.json.JSONArray
//----- end of Lia's code -----
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class MainActivity : AppCompatActivity() {
    private lateinit var log: TextView
    private lateinit var logScroll: ScrollView
    private lateinit var prompt: TextView
    private lateinit var input: EditText
    private lateinit var homeButtons: View
    private lateinit var bridge: PyObject
    private lateinit var protocolFolder: File
    private var waitingForAnswer = false
    //----- Lia's code: the area with one button per option (or Yes / No / Don't know) -----
    private lateinit var choiceScroll: ScrollView
    private lateinit var choiceBox: LinearLayout
    private lateinit var yesButton: Button
    private lateinit var noButton: Button
    private val pickedNumbers = mutableListOf<String>()   // multi-choice: numbers tapped so far
    private var running: String? = null    // "run_visit", "run_test_cases", or null when nothing runs
    //----- end of Lia's code -----

    // MedPsy lives here. "Load model" copies it in from a file the user picked (e.g. from Downloads).
    // Without it the app uses keyword matching.
    private val modelFile by lazy { File(filesDir, "models/medpsy-1.7b-q4_k_m-imat.gguf") }
    private val pickModel = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            copyModel(uri)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main)) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }

        log = findViewById(R.id.log)
        logScroll = findViewById(R.id.logScroll)
        prompt = findViewById(R.id.prompt)
        input = findViewById(R.id.input)
        homeButtons = findViewById(R.id.homeButtons)
        //----- Lia's code: find the option-button area; the old fixed Yes / No buttons start hidden -----
        choiceScroll = findViewById(R.id.choiceScroll)
        choiceBox = findViewById(R.id.choiceBox)
        yesButton = findViewById(R.id.yesButton)
        noButton = findViewById(R.id.noButton)
        yesButton.visibility = View.GONE
        noButton.visibility = View.GONE
        // A taller answer box: always 2 lines, grows to 5, long answers wrap so the CHW can read them back.
        // The keyboard still shows Send (not a new-line key), so Send on the keyboard still sends.
        input.setSingleLine(false)
        input.minLines = 2
        input.maxLines = 5
        input.setHorizontallyScrolling(false)
        input.imeOptions = EditorInfo.IME_ACTION_SEND
        input.setRawInputType(InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES)
        //----- end of Lia's code -----
        //----- Lia's code: the menu (top left) and the Back button (round 2) -----
        findViewById<TextView>(R.id.appTitle).text = applicationInfo.loadLabel(packageManager)
        findViewById<Button>(R.id.menuButton).setOnClickListener { showMenu(it) }
        findViewById<Button>(R.id.backButton).setOnClickListener { goBack() }
        //----- end of Lia's code -----
        findViewById<Button>(R.id.newVisitButton).setOnClickListener { startVisit("run_visit") }
        findViewById<Button>(R.id.testCasesButton).setOnClickListener { startVisit("run_test_cases") }
        findViewById<Button>(R.id.loadModelButton).setOnClickListener { pickModel.launch(arrayOf("*/*")) }
        findViewById<Button>(R.id.shareButton).setOnClickListener { shareVisits() }

        findViewById<Button>(R.id.sendButton).setOnClickListener { sendAnswer(input.text.toString()) }
        findViewById<Button>(R.id.yesButton).setOnClickListener { sendAnswer("y") }
        findViewById<Button>(R.id.noButton).setOnClickListener { sendAnswer("n") }
        findViewById<Button>(R.id.skipButton).setOnClickListener { sendAnswer("") }
        input.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendAnswer(input.text.toString())
            }
            true
        }

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        bridge = Python.getInstance().getModule("app_bridge")
        protocolFolder = copyProtocolsToPhone()
        showHome("")
    }

    private fun showHome(message: String) {
        val modelStatus = if (modelFile.exists()) {
            "MedPsy: ready (${modelFile.length() shr 20} MB)."
        } else {
            "MedPsy: not on this phone yet. Tap Load model and pick medpsy-1.7b-q4_k_m-imat.gguf " +
                "from Downloads. Until then, visits use keyword matching (no AI)."
        }
        val intro = "New visit: a patient visit, typed by you.\n" +
            "Run test cases: the phone plays TC01-TC05 from the answer sheet by itself (a few minutes).\n" + modelStatus
        prompt.text = if (message.isEmpty()) intro else message + "\n\n" + intro
        homeButtons.visibility = View.VISIBLE
    }

    // Copies the picked .gguf file into the app (about a minute for 1.3 GB), then MedPsy is used offline.
    private fun copyModel(uri: Uri) {
        homeButtons.visibility = View.GONE
        Thread {
            try {
                val name = fileName(uri)
                if (!name.endsWith(".gguf")) {
                    runOnUiThread { showHome("That is not a model file (.gguf): $name") }
                    return@Thread
                }
                modelFile.parentFile?.mkdirs()
                val partial = File(modelFile.path + ".part")
                contentResolver.openInputStream(uri)!!.use { source ->
                    partial.outputStream().use { target ->
                        val buffer = ByteArray(1 shl 20)
                        var copied = 0L
                        var lastShown = 0L
                        while (true) {
                            val count = source.read(buffer)
                            if (count < 0) {
                                break
                            }
                            target.write(buffer, 0, count)
                            copied += count
                            if (copied - lastShown >= (50L shl 20)) {
                                lastShown = copied
                                val megabytes = copied shr 20
                                runOnUiThread { prompt.text = "Copying the model... $megabytes MB" }
                            }
                        }
                    }
                }
                modelFile.delete()
                partial.renameTo(modelFile)
                runOnUiThread { showHome("Model copied. New visits and test cases now use MedPsy.") }
            } catch (error: Throwable) {
                runOnUiThread { showHome("Could not copy the model: $error") }
            }
        }.start()
    }

    // Puts every saved visit (and every test-case run) into one .zip and opens the phone's share menu,
    // so the records can be emailed or saved to Drive without a computer.
    private fun shareVisits() {
        val visits = File(filesDir, "visits")
        val files = visits.walkTopDown().filter { it.isFile }.toList()
        if (files.isEmpty()) {
            showHome("No visits saved yet. Do a visit or run the test cases first.")
            return
        }
        val shareFolder = File(cacheDir, "share")
        shareFolder.deleteRecursively()
        shareFolder.mkdirs()
        val time = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val zip = File(shareFolder, "intake_visits_$time.zip")
        ZipOutputStream(zip.outputStream()).use { out ->
            for (file in files) {
                out.putNextEntry(ZipEntry(file.relativeTo(visits).path))
                file.inputStream().use { it.copyTo(out) }
                out.closeEntry()
            }
        }
        val uri = FileProvider.getUriForFile(this, "$packageName.files", zip)
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "application/zip"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, "IntakeApp visits ($time)")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(send, "Share visit files (${files.size} files)"))
    }

    private fun fileName(uri: Uri): String {
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                return cursor.getString(0) ?: ""
            }
        }
        return uri.lastPathSegment ?: ""
    }

    // pythonFunction: "run_visit" (a real visit) or "run_test_cases" (the phone plays the test cases itself)
    private fun startVisit(pythonFunction: String) {
        //----- Lia's code: remember what is running, for the menu -----
        running = pythonFunction
        //----- end of Lia's code -----
        homeButtons.visibility = View.GONE
        waitingForAnswer = false
        log.text = ""
        prompt.text = "Starting..."
        val saveFolder = File(filesDir, "visits")
        val screen = Screen()
        // The visit runs in the background, so the screen stays responsive while it waits for answers.
        // It gets a big stack (64 MB) because llama.cpp's grammar checks go deep.
        Thread(null, {
            try {
                if (modelFile.exists()) {
                    LlmEngine.backendDir = applicationInfo.nativeLibraryDir
                    LlmEngine.threads = minOf(4, Runtime.getRuntime().availableProcessors())
                }
                bridge.callAttr(pythonFunction, screen, protocolFolder.absolutePath, saveFolder.absolutePath,
                    modelFile.absolutePath)
            } catch (error: Throwable) {
                runOnUiThread {
                    //----- Lia's code: nothing runs any more -----
                    running = null
                    //----- end of Lia's code -----
                    addToLog("\nSomething went wrong:\n$error")
                    homeButtons.visibility = View.VISIBLE
                }
            }
        }, "visit", 64L * 1024 * 1024).start()
    }

    private fun sendAnswer(text: String) {
        if (!waitingForAnswer) {
            return
        }
        waitingForAnswer = false
        addToLog(">> " + prompt.text + "  " + text)
        input.setText("")
        prompt.text = ""
        //----- Lia's code: clear the buttons once an answer is sent -----
        clearChoices()
        //----- end of Lia's code -----
        bridge.callAttr("answer", text)
    }

    private fun addToLog(text: String) {
        log.append(text + "\n")
        logScroll.post { logScroll.fullScroll(ScrollView.FOCUS_DOWN) }
    }

    //----- Lia's code: styled lines in the visit log, and buttons that fit each question -----
    // style comes from screen_ui.line_style(): "section", "question", "red_flag", "summary" or "plain".
    private fun addStyledToLog(text: String, style: String) {
        val line = SpannableString(text + "\n")
        val end = text.length
        if (end > 0) {
            when (style) {
                "section" -> {    // e.g. "--- Past medical history ---": dark blue, bold, bigger
                    line.setSpan(StyleSpan(Typeface.BOLD), 0, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    line.setSpan(RelativeSizeSpan(1.2f), 0, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    line.setSpan(ForegroundColorSpan(Color.parseColor("#1A237E")), 0, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                }
                "question" -> {   // every question title: purple and bold, so it stands out from the options
                    line.setSpan(StyleSpan(Typeface.BOLD), 0, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    line.setSpan(RelativeSizeSpan(1.1f), 0, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    line.setSpan(ForegroundColorSpan(Color.parseColor("#6A1B9A")), 0, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                }
                "red_flag" -> {
                    line.setSpan(StyleSpan(Typeface.BOLD), 0, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                    line.setSpan(ForegroundColorSpan(Color.parseColor("#B71C1C")), 0, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                }
                "summary" -> line.setSpan(StyleSpan(Typeface.BOLD), 0, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
        }
        log.append(line)
        logScroll.post { logScroll.fullScroll(ScrollView.FOCUS_DOWN) }
    }

    private fun clearChoices() {
        choiceBox.removeAllViews()
        choiceScroll.visibility = View.GONE
        pickedNumbers.clear()
    }

    // kind: "options" (one button per option), "yes_no", "red_flag" (Yes / No / Don't know),
    // "choice" (female / male) or "text" (typing only). Each button sends exactly what a CHW would type.
    private fun showChoices(kind: String, buttonsJson: String, multi: Boolean) {
        clearChoices()
        val buttons = JSONArray(buttonsJson)
        input.hint = when (kind) {
            "options" -> if (multi) "Tap all that apply, then Send, or type the patient's words"
                         else "Tap an option, or type the patient's words"
            "yes_no", "red_flag", "choice" -> "Tap a button"
            else -> "Type here, then Send"
        }
        if (buttons.length() == 0) {
            return
        }
        // Options go one per row (labels can be long); Yes / No style buttons go side by side.
        choiceBox.orientation = if (kind == "options") LinearLayout.VERTICAL else LinearLayout.HORIZONTAL
        for (i in 0 until buttons.length()) {
            val pair = buttons.getJSONArray(i)
            val sendText = pair.getString(0)
            val label = pair.getString(1)
            val button = Button(this)
            button.isAllCaps = false
            button.text = if (kind == "options") "$sendText. $label" else label
            if (kind == "options") {
                button.layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT)
            } else {
                button.layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            }
            button.setOnClickListener {
                if (kind == "options" && multi) {
                    // Multi-choice: tapping adds or removes the number; Send sends them all ("2,9").
                    if (pickedNumbers.contains(sendText)) {
                        pickedNumbers.remove(sendText)
                        button.alpha = 1.0f
                    } else {
                        pickedNumbers.add(sendText)
                        button.alpha = 0.5f
                    }
                    input.setText(pickedNumbers.joinToString(","))
                } else {
                    sendAnswer(sendText)
                }
            }
            choiceBox.addView(button)
        }
        choiceScroll.visibility = View.VISIBLE
        // Long lists (e.g. 52 complaints) scroll inside a box of at most about a third of the screen.
        choiceScroll.post {
            input.requestFocus()    // keep the cursor in the answer box after the buttons are drawn
            val maxHeight = resources.displayMetrics.heightPixels / 3
            val params = choiceScroll.layoutParams
            params.height = if (choiceBox.height > maxHeight) maxHeight else ViewGroup.LayoutParams.WRAP_CONTENT
            choiceScroll.layoutParams = params
            choiceScroll.scrollTo(0, 0)
        }
    }

    // Back: undo the last answer. The Python side replays the visit without it (visit_replay.py).
    private fun goBack() {
        if (!waitingForAnswer || running != "run_visit") {
            return
        }
        waitingForAnswer = false
        clearChoices()
        input.setText("")
        prompt.text = "Going back..."
        bridge.callAttr("answer", "[[back]]")
    }

    // The menu (top left). During a visit: End this visit. Otherwise: New visit, Run test cases,
    // Load model, Share visit files (the same as the big buttons on the start screen).
    private fun showMenu(anchor: View) {
        val popup = PopupMenu(this, anchor)
        when (running) {
            "run_visit" -> popup.menu.add(0, 1, 0, "End this visit")
            "run_test_cases" -> popup.menu.add(0, 0, 0, "Test cases are running...").isEnabled = false
            else -> {
                popup.menu.add(0, 2, 0, "New visit")
                popup.menu.add(0, 3, 1, "Run test cases")
                popup.menu.add(0, 4, 2, "Load model")
                popup.menu.add(0, 5, 3, "Share visit files")
            }
        }
        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                1 -> confirmEndVisit()
                2 -> startVisit("run_visit")
                3 -> startVisit("run_test_cases")
                4 -> pickModel.launch(arrayOf("*/*"))
                5 -> shareVisits()
            }
            true
        }
        popup.show()
    }

    private fun confirmEndVisit() {
        AlertDialog.Builder(this)
            .setTitle("End this visit?")
            .setMessage("The answers so far will not be saved.")
            .setPositiveButton("End visit") { _, _ ->
                waitingForAnswer = false
                clearChoices()
                input.setText("")
                prompt.text = "Ending the visit..."
                bridge.callAttr("answer", "[[end]]")
            }
            .setNegativeButton("Keep going", null)
            .show()
    }
    //----- end of Lia's code -----

    // The Python code calls these three functions from its background thread.
    inner class Screen {
        fun show(text: String) {
            runOnUiThread { addToLog(text) }
        }

        //----- Lia's code: show one line with its style, and ask with the buttons that fit the question -----
        fun showStyled(text: String, style: String) {
            runOnUiThread { addStyledToLog(text, style) }
        }

        fun clearLog() {
            runOnUiThread { log.text = "" }
        }

        fun ended(message: String) {
            runOnUiThread {
                running = null
                clearChoices()
                showHome(message)
            }
        }

        fun askWith(question: String, kind: String, buttonsJson: String, multi: Boolean) {
            runOnUiThread {
                prompt.text = question.trim()
                showChoices(kind, buttonsJson, multi)
                waitingForAnswer = true
                // The cursor is always in the answer box, so the CHW can type without tapping it first.
                input.requestFocus()
                if (kind == "text") {
                    // Typing questions (the patient's words, a duration, a name): open the keyboard too.
                    val keyboard = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
                    keyboard.showSoftInput(input, InputMethodManager.SHOW_IMPLICIT)
                }
            }
        }
        //----- end of Lia's code -----

        fun ask(question: String) {
            runOnUiThread {
                prompt.text = question.trim()
                waitingForAnswer = true
            }
        }

        fun finished(savedPath: String) {
            runOnUiThread {
                //----- Lia's code: no buttons left over after the visit; nothing runs any more -----
                clearChoices()
                running = null
                //----- end of Lia's code -----
                prompt.text = "Finished. Saved on the phone:\n$savedPath"
                homeButtons.visibility = View.VISIBLE
            }
        }
    }

    // Our Python code reads the protocol files from a normal folder, so copy them out of the app.
    private fun copyProtocolsToPhone(): File {
        val folder = File(filesDir, "protocols")
        folder.mkdirs()
        for (name in assets.list("") ?: emptyArray()) {
            if (!name.endsWith(".json")) {
                continue
            }
            assets.open(name).use { input ->
                File(folder, name).outputStream().use { file -> input.copyTo(file) }
            }
        }
        return folder
    }
}
