// Connects the Kotlin LlmEngine object to engine.cpp.
#include <jni.h>
#include <string>

#include "engine.h"

static std::string g_error;

static std::string to_string(JNIEnv * env, jstring text) {
    const char * chars = env->GetStringUTFChars(text, nullptr);
    std::string result(chars);
    env->ReleaseStringUTFChars(text, chars);
    return result;
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_example_intakeapp_LlmEngine_nativeLoad(JNIEnv * env, jobject, jstring model_path, jint context_size,
                                                jint threads, jstring backend_dir) {
    g_error.clear();
    return engine_load(to_string(env, model_path), context_size, threads, to_string(env, backend_dir), g_error);
}

// Returns UTF-8 bytes (Kotlin turns them into a String), so any character the model writes is safe.
extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_example_intakeapp_LlmEngine_nativeGenerate(JNIEnv * env, jobject, jstring prompt, jint max_tokens,
                                                    jstring grammar) {
    g_error.clear();
    std::string text = engine_generate(to_string(env, prompt), max_tokens, to_string(env, grammar), g_error);
    jbyteArray bytes = env->NewByteArray((jsize) text.size());
    env->SetByteArrayRegion(bytes, 0, (jsize) text.size(), (const jbyte *) text.data());
    return bytes;
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_example_intakeapp_LlmEngine_nativeLastError(JNIEnv * env, jobject) {
    return env->NewStringUTF(g_error.c_str());
}

extern "C" JNIEXPORT jintArray JNICALL
Java_com_example_intakeapp_LlmEngine_nativeLastCounts(JNIEnv * env, jobject) {
    jint counts[3] = { engine_last_prompt_tokens(), engine_last_reused_tokens(), engine_last_output_tokens() };
    jintArray result = env->NewIntArray(3);
    env->SetIntArrayRegion(result, 0, 3, counts);
    return result;
}
