// A small llama.cpp engine for the Intelehealth intake app.
// It does what our Python code asks of llama-cpp-python: complete a prompt, greedily,
// optionally limited by a GBNF grammar, and stop at the model's end token.
#pragma once
#include <string>

// backend_dir: folder with the ggml CPU backend libraries ("" when they are linked in).
bool engine_load(const std::string & model_path, int n_ctx, int n_threads,
                 const std::string & backend_dir, std::string & error);

// Returns the generated text. grammar = "" means no grammar.
std::string engine_generate(const std::string & prompt, int max_tokens,
                            const std::string & grammar, std::string & error);

int engine_last_prompt_tokens();   // tokens in the last prompt
int engine_last_reused_tokens();   // of those, how many were already in memory from the call before
int engine_last_output_tokens();   // tokens written in the last call

void engine_free();
