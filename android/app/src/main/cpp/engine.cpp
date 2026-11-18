#include "engine.h"

#include <algorithm>
#include <vector>

#include "common.h"
#include "ggml-backend.h"
#include "llama.h"

static llama_model             * g_model   = nullptr;
static llama_context           * g_context = nullptr;
static const llama_vocab       * g_vocab   = nullptr;
static int                       g_n_batch = 512;
static std::vector<llama_token>  g_in_memory;   // the tokens whose results are in the model's memory now

static int g_last_prompt_tokens = 0;
static int g_last_reused_tokens = 0;
static int g_last_output_tokens = 0;

bool engine_load(const std::string & model_path, int n_ctx, int n_threads,
                 const std::string & backend_dir, std::string & error) {
    if (g_model) {
        return true;   // already loaded
    }
    if (!backend_dir.empty()) {
        ggml_backend_load_all_from_path(backend_dir.c_str());   // picks the best CPU variant for this phone
    }
    llama_backend_init();

    llama_model_params model_params = llama_model_default_params();
    g_model = llama_model_load_from_file(model_path.c_str(), model_params);
    if (!g_model) {
        error = "could not load the model: " + model_path;
        return false;
    }

    llama_context_params context_params = llama_context_default_params();
    context_params.n_ctx = n_ctx;
    context_params.n_batch = g_n_batch;
    context_params.n_threads = n_threads;
    context_params.n_threads_batch = n_threads;
    g_context = llama_init_from_model(g_model, context_params);
    if (!g_context) {
        error = "could not create the model context";
        llama_model_free(g_model);
        g_model = nullptr;
        return false;
    }
    g_vocab = llama_model_get_vocab(g_model);
    g_in_memory.clear();
    return true;
}

// Runs the tokens through the model, starting at position start. Only the last token's result is kept.
static bool decode(const std::vector<llama_token> & tokens, size_t start, std::string & error) {
    common_batch batch(g_context);
    for (size_t i = start; i < tokens.size(); i += g_n_batch) {
        size_t end = std::min(tokens.size(), i + g_n_batch);
        batch.clear();
        for (size_t j = i; j < end; j++) {
            bool last = (j == tokens.size() - 1);
            batch.add(tokens[j], (llama_pos) j, 0, last);
        }
        if (llama_process(g_context, LLAMA_PROCESS_TYPE_DECODE, batch.get()) != 0) {
            error = "the model could not process the prompt";
            return false;
        }
    }
    return true;
}

std::string engine_generate(const std::string & prompt, int max_tokens,
                            const std::string & grammar, std::string & error) {
    g_last_prompt_tokens = g_last_reused_tokens = g_last_output_tokens = 0;
    if (!g_context) {
        error = "the model is not loaded";
        return "";
    }

    // The prompt contains chat markers like <|im_start|>, so special tokens are parsed.
    std::vector<llama_token> tokens = common_tokenize(g_vocab, prompt, true, true);
    if (tokens.empty()) {
        error = "empty prompt";
        return "";
    }
    if ((int) tokens.size() + max_tokens > (int) llama_n_ctx(g_context)) {
        error = "the prompt is too long for the context";
        return "";
    }

    // Reuse the start of the prompt that is still in memory from the last call (like llama-cpp-python).
    size_t same = 0;
    while (same < g_in_memory.size() && same < tokens.size() && g_in_memory[same] == tokens[same]) {
        same++;
    }
    if (same == tokens.size()) {
        same--;   // the last prompt token must be run again to get its result
    }
    llama_memory_t memory = llama_get_memory(g_context);
    if (!llama_memory_seq_rm(memory, 0, (llama_pos) same, -1)) {
        llama_memory_clear(memory, true);
        same = 0;
    }
    g_in_memory.assign(tokens.begin(), tokens.begin() + same);
    g_last_prompt_tokens = (int) tokens.size();
    g_last_reused_tokens = (int) same;

    if (!decode(tokens, same, error)) {
        llama_memory_clear(memory, true);
        g_in_memory.clear();
        return "";
    }
    g_in_memory = tokens;

    // Greedy choice (like temperature 0), limited by the grammar if there is one.
    llama_sampler * sampler = llama_sampler_chain_init(llama_sampler_chain_default_params());
    if (!grammar.empty()) {
        llama_sampler * grammar_sampler = llama_sampler_init_grammar(g_vocab, grammar.c_str(), "root");
        if (!grammar_sampler) {
            llama_sampler_free(sampler);
            error = "the grammar could not be read";
            return "";
        }
        llama_sampler_chain_add(sampler, grammar_sampler);
    }
    llama_sampler_chain_add(sampler, llama_sampler_init_greedy());

    std::string text;
    for (int i = 0; i < max_tokens; i++) {
        llama_token token = llama_sampler_sample(sampler, g_context, -1);
        if (llama_vocab_is_eog(g_vocab, token)) {
            break;
        }
        text += common_token_to_piece(g_vocab, token, false);
        g_last_output_tokens++;

        g_in_memory.push_back(token);
        if (!decode(g_in_memory, g_in_memory.size() - 1, error)) {
            break;
        }
    }
    llama_sampler_free(sampler);
    return text;
}

int engine_last_prompt_tokens() { return g_last_prompt_tokens; }
int engine_last_reused_tokens() { return g_last_reused_tokens; }
int engine_last_output_tokens() { return g_last_output_tokens; }

void engine_free() {
    if (g_context) { llama_free(g_context); g_context = nullptr; }
    if (g_model)   { llama_model_free(g_model); g_model = nullptr; }
    g_in_memory.clear();
}
