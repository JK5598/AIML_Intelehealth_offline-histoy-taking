import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.chaquopy)
}

// Paths that differ per computer live in android/local.properties (not on GitHub):
//   protocols.dir = folder with the Intelehealth v2 "All Protocols (JSON)" files
//   python.build  = a Python on this computer with the same version as the app's Python (3.14)
val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
val protocolsDir = localProperties.getProperty("protocols.dir")
    ?: error("Add protocols.dir=<path to 'All Protocols (JSON)'> to android/local.properties")
val buildPythonPath = localProperties.getProperty("python.build") ?: "python3.14"

android {
    namespace = "com.example.intakeapp"
    ndkVersion = "30.0.16248370"   // the NDK installed in Android Studio's SDK Manager
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.intakeapp"
        minSdk = 24
        targetSdk = 37
        versionCode = 2
        versionName = "1.1"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            abiFilters.add("arm64-v8a")   // our emulator and most phones
        }

        // MedPsy runs with llama.cpp, built for the phone with the same settings as llama.cpp's own
        // Android example (examples/llama.android). BACKEND_DL + CPU_ALL_VARIANTS builds one CPU library
        // per kind of phone chip; the app picks the best one when it starts.
        externalNativeBuild {
            cmake {
                arguments += listOf(
                    "-DCMAKE_BUILD_TYPE=Release",
                    "-DBUILD_SHARED_LIBS=ON",
                    "-DLLAMA_BUILD_APP=OFF",
                    "-DLLAMA_BUILD_COMMON=ON",
                    "-DLLAMA_OPENSSL=OFF",
                    "-DGGML_NATIVE=OFF",
                    "-DGGML_BACKEND_DL=ON",
                    "-DGGML_CPU_ALL_VARIANTS=ON",
                    "-DGGML_LLAMAFILE=OFF",
                    "-DGGML_OPENMP=OFF",   // ggml's own threads; OpenMP would need an extra libomp.so
                )
            }
        }
    }

    buildTypes {
        release {
            optimization {
                enable = true
                packageScope = setOf("androidx.**", "kotlin.**", "kotlinx.**")
            }
        }
    }
    externalNativeBuild {
        cmake {
            path("src/main/cpp/CMakeLists.txt")
            version = "4.1.2"   // the CMake installed in Android Studio's SDK Manager
        }
    }
    // Keep the native libraries as real files on the phone, so llama.cpp can find its CPU libraries.
    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation(libs.androidx.activity.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.constraintlayout)
    implementation(libs.androidx.core.ktx)
    implementation(libs.material)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
}

// Our Python prototype lives one folder above android/ (intake_prototype). The app uses those same
// files, so a fix there is in the app at the next build. Only the app's own modules are copied.
val appPythonFiles = listOf(
    "main.py", "intake.py", "intake_group.py", "followup.py", "protocols.py", "negation.py",
    "red_flags.py", "repeated_questions.py", "summary.py", "explanations.py", "explanations.json",
    "keyword_mapper.py", "ai_mapper.py",
    // for the "Run test cases" button: the evaluation's simulated patient and CHW, and the 5 test cases
    "sim_patient.py", "judge.py", "eval_cases.json", "eval_patient_answers.json",
)
val copyPythonCode = tasks.register<Sync>("copyPythonCode") {
    from(rootProject.file("..")) { include(appPythonFiles) }
    into(layout.buildDirectory.dir("python-code"))
}
tasks.configureEach {
    if (name != "copyPythonCode" && name.contains("Python")) {
        dependsOn(copyPythonCode)
    }
}

chaquopy {
    defaultConfig {
        version = "3.14"
        buildPython(buildPythonPath)
    }
    sourceSets {
        getByName("main") {
            srcDir("build/python-code")
        }
    }
}

// The protocol JSON files go into the app as assets; MainActivity copies them to the phone on start.
androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addStaticSourceDirectory(protocolsDir)
    }
}

