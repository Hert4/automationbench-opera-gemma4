# Runbook — serving open-weight models for AutomationBench 600

Hardware: 8× H200 (141 GB each). Server: SGLang 0.5.12 in a container image carrying the FlashQLA
linear-attention prefill kernel (`ductransa01/sglang-flashqla:combo-2606`). Benchmark harness:
`uv run auto-bench` from [zapier/AutomationBench](https://github.com/zapier/AutomationBench) 1.0.5.

## Serve commands

`beyoru/Opera` — 27B, 48 of 64 layers are GDN linear attention, so KV cache is cheap and one GPU
is enough:

```bash
python3 -m sglang.launch_server --model-path beyoru/Opera \
  --host 0.0.0.0 --port 30011 \
  --linear-attn-prefill-backend flashqla \
  --reasoning-parser qwen3 --tool-call-parser qwen3_coder \
  --mem-fraction-static 0.85
```

`Qwen/Qwen3.6-27B` (base) — tp 2:

```bash
python3 -m sglang.launch_server --model-path Qwen/Qwen3.6-27B --served-model-name Qwen3.6-27B \
  --host 0.0.0.0 --port 30013 --tp 2 \
  --linear-attn-prefill-backend flashqla \
  --reasoning-parser qwen3 --tool-call-parser qwen3_coder \
  --mem-fraction-static 0.85
```

`beyoru/Ops-I` — tp 4:

```bash
python3 -m sglang.launch_server --model-path beyoru/Ops-I --served-model-name Ops-I \
  --host 0.0.0.0 --port 30014 --tp 4 \
  --linear-attn-prefill-backend flashqla \
  --reasoning-parser qwen3 --tool-call-parser qwen3_coder \
  --mem-fraction-static 0.85
```

`gemma-4-31B-it` — full attention + SWA, needs tp 4 (see trap 3) and a patched chat template to
enable thinking (trap 2): port 30012, `--tp 4`, `--chat-template /tpl/gemma4_think.jinja`.

## Bench command

```bash
uv run auto-bench --model <served-model-name> \
  --base-url http://127.0.0.1:<port>/v1 --api-key EMPTY \
  --max-steps 50 --max-concurrent 16 --save-every 1 \
  --export-json <model>_ab600.json > <model>_ab600.log 2>&1
```

Write the log straight to a file. Piping through `tail` buffers the whole stream and you go blind
on progress.

## Four traps, each paid for in wasted hours

### 1. `--tool-call-parser auto` picks the wrong parser for Qwen3.6

SGLang 0.5.12 auto-detects `qwen`, and that parser cannot read Qwen3.6's XML tool calls:

```xml
<tool_call><function=get_weather><parameter=city>Ha Noi</parameter></function></tool_call>
```

`finish_reason` comes back as `tool_calls` while the `tool_calls` field is **empty** — the agent
never acts, so **every assertion fails, 0%**. Tell-tale sign: ~1,400 tokens per task instead of
110-160K. Always pass `--tool-call-parser qwen3_coder` explicitly. (SGLang nightly detects it
correctly; 0.5.12 does not.)

### 2. Gemma 4 has thinking, but it is off by default

`chat_template.jinja` line 186: `set enable_thinking = enable_thinking | default(false)`. No
server flag turns it on. Patch the template to `default(true)`, mount it, and pass
`--chat-template /tpl/gemma4_think.jinja`. Skip this and Gemma is scored without thinking while
Qwen3.6 is scored with it — not a fair comparison.

Related: if you go through an LLM gateway, verify it does not strip `chat_template_kwargs`. Some
do, which silently disables thinking no matter what you send.

### 3. Gemma 4 at tp 1 is strangled by KV cache

| | tp=1 | tp=4 |
| --- | --- | --- |
| `max_total_num_tokens` | 85,385 | **580,398** |
| concurrent requests served | 4 (12 queued) | **15 (0 queued)** |
| speed | 62.3 s/task | **~10 s/task** |
| ETA for 600 tasks | ~45 h | **~2 h** |

AutomationBench tasks carry 100-160K tokens of context. Gemma 4 uses full attention + SWA, so KV
is expensive. Opera, at the same parameter scale, runs fine on a single GPU because 48 of its 64
layers are GDN linear attention. That contrast is arguably a more useful result than the pass
rates.

### 4. `--save-every 1` saves nothing

`verifiers` runs the whole rollout batch and exports only at the end — nothing lands on disk while
the run is in flight. Interrupt it and you lose everything; `--recover` is useless because no
`.partial.json` exists. If you need crash resistance, split the run into batches with
`--skip N --num-examples M`.

## Reading partial results

`pass_rate` is U-shaped in n, because the benchmark walks domains sequentially and the middle
stretch is hardest. Opera's actual trajectory:

```
n:      10     20     30     50    100    150    200    250    277    360    600
pass:  20.0%  15.0%  13.3%  10.0%   6.7%   6.3%   7.8%   9.6%  10.4%   8.5%   8.5%
part:  0.356  0.356  0.338  0.351  0.379  0.427  0.461  0.487  0.501  0.513  0.442
```

Any number read before all 600 tasks finish is off, and off in a direction you cannot predict.
Compare two models only at the same n, in absolute passed-task counts — at small n a single task
is worth 5-6 percentage points. `partial_credit` rises monotonically and is the steadier signal.

## Monitoring over SSH

`pgrep -f auto-bench` matches its own command line when run through SSH. Use a bracket pattern:

```bash
ps -eo pid,etime,cmd --no-headers | grep '[a]uto-bench --model'
```
