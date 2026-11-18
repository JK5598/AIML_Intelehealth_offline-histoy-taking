package com.example.intakeapp

import android.os.Bundle
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
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
        prompt.text = "New visit: a patient visit, typed by you.\n" +
            "Run test cases: the phone plays TC01-TC05 from the answer sheet by itself (a few minutes)."
        homeButtons.visibility = View.VISIBLE
    }

    // pythonFunction: "run_visit" (a real visit) or "run_test_cases" (the phone plays the test cases itself)
    private fun startVisit(pythonFunction: String) {
        homeButtons.visibility = View.GONE
        waitingForAnswer = false
        log.text = ""
        prompt.text = "Starting..."
        val saveFolder = File(filesDir, "visits")
        // The adb commands in the README copy MedPsy here. Without it the app uses keyword matching.
        val modelFile = File(filesDir, "models/medpsy-1.7b-q4_k_m-imat.gguf")
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
