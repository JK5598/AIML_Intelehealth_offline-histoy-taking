package com.example.intakeapp

// MedPsy on the phone: a thin Kotlin layer over llama.cpp (src/main/cpp). The Python code calls it
// through the llama_cpp stand-in in src/main/python/llama_cpp.
object LlmEngine {
    init {
        System.loadLibrary("intake_llm")
    }

    // Folder with llama.cpp's CPU libraries; MainActivity sets it before the first load.
    var backendDir = ""
    var threads = 4

    private external fun nativeLoad(modelPath: String, contextSize: Int, threads: Int, backendDir: String): Boolean
    private external fun nativeGenerate(prompt: String, maxTokens: Int, grammar: String): ByteArray
    private external fun nativeLastError(): String
    private external fun nativeLastCounts(): IntArray

    @JvmStatic
    fun load(modelPath: String, contextSize: Int): Boolean = nativeLoad(modelPath, contextSize, threads, backendDir)

    @JvmStatic
    fun generate(prompt: String, maxTokens: Int, grammar: String): String =
        String(nativeGenerate(prompt, maxTokens, grammar), Charsets.UTF_8)

    @JvmStatic
    fun lastError(): String = nativeLastError()

    // [tokens in the prompt, of those already in memory, tokens written]
    @JvmStatic
    fun lastCounts(): IntArray = nativeLastCounts()
}
