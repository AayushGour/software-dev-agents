"""Minimal Hermes-style tool-calling agent over llama_cpp.

Drives a local GGUF model in a tool loop. Parses Hermes/Qwen `<tool_call>{json}</tool_call>`
tags, executes hermes_tools, feeds results back, until the model emits `<done/>`.

Used by run.py (seam 1). Also runnable directly for a single task — see __main__.
"""

import os
import re
import json

import hermes_tools

TOOL_FUNCS = hermes_tools.TOOLS

TOOLS_DOC = """
You have tools. To call one, output EXACTLY this and nothing else:
<tool_call>{"name": "<tool>", "arguments": {<args>}}</tool_call>

Tools:
- write_file(path, content)   create/overwrite a file
- read_file(path)
- append_file(path, content)
- list_dir(path)
- grep(pattern, path)
- run(cmd)                    shell command in the project dir

Rules: one tool call per message. After you have finished the whole task, reply with <done/>.
"""

_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
_FENCE_RE = re.compile(r"```(?:html|js|javascript|python|css)?\s*(.*?)```", re.S)
_THINK_RE = re.compile(r"<think>.*?</think>", re.S)

_LLM = None


def _load(model_path: str, n_ctx: int):
    global _LLM
    if _LLM is None:
        from llama_cpp import Llama
        _LLM = Llama(model_path=model_path, n_ctx=n_ctx, n_gpu_layers=-1, verbose=False)
    return _LLM


def run_agent(system_prompt: str, user_prompt: str, model_path: str,
              max_steps: int = 8, n_ctx: int = 8192, max_tokens: int = 4096,
              verbose: bool = True) -> str:
    llm = _load(model_path, n_ctx)
    messages = [
        {"role": "system", "content": system_prompt + "\n" + TOOLS_DOC},
        {"role": "user", "content": user_prompt},
    ]
    for step in range(max_steps):
        out = llm.create_chat_completion(messages=messages, max_tokens=max_tokens, temperature=0.3)
        text = out["choices"][0]["message"]["content"] or ""
        visible = _THINK_RE.sub("", text).strip()
        messages.append({"role": "assistant", "content": text})

        m = _CALL_RE.search(visible)
        if m:
            try:
                call = json.loads(m.group(1))
                name, args = call["name"], call.get("arguments", {})
                result = str(TOOL_FUNCS[name](**args))
            except Exception as e:
                result = f"ERROR: {e}"
            if verbose:
                print(f"[step {step}] tool {m.group(1)[:80]}... -> {result[:100]}")
            messages.append({"role": "user", "content": f"<tool_result>{result}</tool_result>"})
            continue

        # fallback: model dumped a code block instead of a tool call — capture it
        fence = _FENCE_RE.search(visible)
        if fence and "write" not in visible.lower()[:0]:  # only if no tool call happened
            code = fence.group(1).strip()
            target = "index.html" if "<html" in code.lower() or "<!doctype" in code.lower() else "output.txt"
            hermes_tools.write_file(target, code)
            if verbose:
                print(f"[step {step}] captured code block -> wrote {target} ({len(code)} bytes)")
            return f"wrote {target} from code block"

        if "<done" in visible.lower():
            if verbose:
                print(f"[step {step}] <done/>")
            return visible
        if verbose:
            print(f"[step {step}] no tool call / no done; nudging")
        messages.append({"role": "user", "content": "Continue. Use a <tool_call> or reply <done/>."})
    return "max steps reached"


if __name__ == "__main__":
    # direct single-task run:
    #   HERMES_PROJECT=<dir> python hermes_agent.py <model.gguf> "<system>" "<task>"
    import sys
    model = sys.argv[1]
    system = sys.argv[2] if len(sys.argv) > 2 else "You are a senior software engineer."
    task = sys.argv[3] if len(sys.argv) > 3 else "Say hello and reply <done/>."
    print(run_agent(system, task, model, max_steps=int(os.environ.get("MAX_STEPS", "8"))))
