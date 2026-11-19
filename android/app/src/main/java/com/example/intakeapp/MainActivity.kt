package com.example.intakeapp

import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File

class MainActivity : AppCompatActivity() {
    private lateinit var log: TextView
    private lateinit var logScroll: ScrollView
    private lateinit var prompt: TextView
    private lateinit var input: EditText
    private lateinit var homeButtons: View
    private lateinit var bridge: PyObject
    private lateinit var protocolFolder: File
    private var waitingForAnswer = false

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
        findViewById<Button>(R.id.newVisitButton).setOnClickListener { startVisit("run_visit") }
        findViewById<Button>(R.id.testCasesButton).setOnClickListener { startVisit("run_test_cases") }
        findViewById<Button>(R.id.loadModelButton).setOnClickListener { pickModel.launch(arrayOf("*/*")) }

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
        bridge.callAttr("answer", text)
    }

    private fun addToLog(text: String) {
        log.append(text + "\n")
        logScroll.post { logScroll.fullScroll(ScrollView.FOCUS_DOWN) }
    }

    // The Python code calls these three functions from its background thread.
    inner class Screen {
        fun show(text: String) {
            runOnUiThread { addToLog(text) }
        }

        fun ask(question: String) {
            runOnUiThread {
                prompt.text = question.trim()
                waitingForAnswer = true
            }
        }

        fun finished(savedPath: String) {
            runOnUiThread {
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
