# Builds llama.cpp and our small engine (engine.cpp + jni.cpp) into the app.
cmake_minimum_required(VERSION 3.22.1)
project(intake_llm C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED true)

# llama.cpp: the same version we tested against llama-cpp-python (b12447, 45/46 identical answers).
# Downloaded once, the first time Android Studio builds the app.
include(FetchContent)
FetchContent_Declare(llama_cpp
    URL https://github.com/ggml-org/llama.cpp/archive/refs/tags/b12447.tar.gz)
FetchContent_MakeAvailable(llama_cpp)

add_library(intake_llm SHARED engine.cpp jni.cpp)
target_link_libraries(intake_llm llama llama-common android log)
