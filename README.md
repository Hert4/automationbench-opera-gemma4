# AutomationBench 600 — open-weight run (Qwen3.6-27B, Opera, Gemma 4 31B, Ops-I)

Full results of the **public 600-task [AutomationBench](https://github.com/zapier/AutomationBench)**
(Zapier, benchmark version 1.0.5, `--toolset api`) on four open-weight models served locally with
SGLang 0.5.12 on 8× H200.

Every task, every assertion, every token count is published — see [`data/`](data/).

- Maintainer: [@Hert4](https://github.com/Hert4)
- Benchmark: [zapier/AutomationBench](https://github.com/zapier/AutomationBench) ([paper](https://arxiv.org/abs/2604.18934)) — all credit for tasks, tools and assertions to Zapier
- Raw run artifacts (full conversation traces, ~350 MB): [HF dataset](https://huggingface.co/datasets/beyoru/automationbench600-open-weight-runs)

## Results

Official AutomationBench metric = **pass rate**: a task counts only if *every* assertion passes.
`partial credit` = fraction of assertions satisfied.

| Model | Pass rate | Passed / 600 | Partial credit | Assertions passed | Wall clock |
| --- | --- | --- | --- | --- | --- |
| gemma-4-31B-it (thinking on) | **10.17%** | 61 | 41.64% | 2749 / 6018 (45.7%) | 2.15 h |
| Qwen3.6-27B (base) | **9.67%** | 58 | 46.00% | 3053 / 6222 (49.1%) | 1.95 h |
| beyoru/Opera (Qwen3.6-27B finetune) | **8.50%** | 51 | 44.20% | 3059 / 6196 (49.4%) | 3.62 h |
| beyoru/Ops-I | *running* | | | | |

Placed against the reference table in the upstream README (those models run at their highest
available reasoning effort; ours ran with no reasoning-effort setting):

| Model | Pass rate |
| --- | --- |
| Claude Opus 4.8 | 30.33% |
| GPT-5.6 Sol | 29.17% |
| GPT-5.6 Terra | 25.83% |
| Claude Fable 5 | 25.83% |
| Claude Sonnet 5 | 24.00% |
| GLM 5.2 | 20.33% |
| Gemini 3.5 Flash | 14.83% |
| **gemma-4-31B-it** | **10.17%** |
| **Qwen3.6-27B base** | **9.67%** |
| **beyoru/Opera** | **8.50%** |

## Per domain

Tasks passed out of 100, with partial credit in parentheses.

| Model | Finance | HR | Marketing | Operations | Sales | Support |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3.6-27B base | 21 (57.7) | 3 (12.4) | 3 (45.1) | 17 (60.9) | 8 (41.4) | 6 (58.4) |
| beyoru/Opera | 17 (49.1) | 1 (10.9) | 5 (51.3) | 19 (61.2) | 7 (36.0) | 2 (56.6) |
| gemma-4-31B-it | 18 (48.7) | 1 (5.2) | 14 (56.3) | 15 (56.2) | 9 (34.3) | 4 (49.1) |

HR is the shared floor: 1-3 tasks out of 100 for every model, partial credit 5-12%. Operations
and finance carry most of the score.

## What actually breaks

### 1. Negative assertions fail almost universally

Assertions of the form "do **not** send this email / do **not** create this row / do **not** post
in this channel" are where these models collapse:

| Model | Positive assertions | Negative assertions |
| --- | --- | --- |
| Qwen3.6-27B base | 2986 / 5637 = 53.0% | 67 / 585 = **11.5%** |
| beyoru/Opera | 2997 / 5634 = 53.2% | 62 / 562 = **11.0%** |
| gemma-4-31B-it | 2664 / 5611 = 47.5% | 85 / 407 = **20.9%** |

Aggregated over the three models, some negative assertion types never pass once:

| Assertion type | Passed / total |
| --- | --- |
| `gmail_message_not_sent` | 0 / 138 |
| `google_sheets_row_not_exists` | 0 / 118 |
| `slack_message_not_in_channel` | 0 / 114 |
| `gmail_message_not_sent_to` | 1 / 119 |

These models do not fail by being unable to act. They fail by acting too much — extra emails,
extra rows, extra Slack posts. Restraint, not capability, is the missing behaviour.

### 2. Most failures are not near-misses

Tasks that failed, by how many assertions they were short:

| Model | Missed 1 | Missed 2 | Missed 3+ |
| --- | --- | --- | --- |
| Qwen3.6-27B base | 68 | 69 | 405 |
| beyoru/Opera | 61 | 73 | 415 |
| gemma-4-31B-it | 62 | 65 | 412 |

~75% of failed tasks miss three or more assertions. Prompt-level polish will not move these; the
workflows are being got wrong wholesale.

### 3. Hardest assertion types overall (3 models aggregated)

| Assertion type | Pass rate | Failures |
| --- | --- | --- |
| `gmail_message_sent_to_with_body_contains` | 43.3% | 1867 |
| `google_sheets_row_exists` | 53.9% | 781 |
| `slack_message_in_channel` | 55.6% | 483 |
| `gmail_message_sent_to` | 60.1% | 440 |
| `gmail_message_sent` | 58.6% | 394 |
| `google_sheets_row_updated` | **20.4%** | 339 |
| `freshdesk_ticket_has_note` | **20.7%** | 169 |

`google_sheets_row_updated` (20.4%) vs `google_sheets_row_exists` (53.9%): these models would
rather append a new row than update the existing one.

### 4. The finetune did not beat its base

Opera is a finetune of Qwen3.6-27B. On identical tasks it lands **7 fewer passes** (51 vs 58) and
1.8 points lower partial credit, while taking 1.9× the wall clock. Assertion-level accuracy is
essentially identical (49.4% vs 49.1%) — Opera loses specifically on *completing every* assertion
of a task, and it burns more steps doing it (63 tasks hit the 50-step ceiling vs 52 for base).

### 5. Step budget

Average 22.6-23.1 steps per task. Tasks hitting the `--max-steps 50` ceiling: base 52, Opera 63,
Gemma 4 **18**. Gemma gives up earlier, which costs partial credit (41.6%, lowest of the three)
but is not what limits its pass rate.

## Reading these numbers correctly

Pass rate over a partial run is **U-shaped in n** — the benchmark runs domains sequentially and the
middle stretch is hardest. Opera measured 20% at n=10, 5.6% at n=120, 8.5% at n=600. Any number
taken before all 600 tasks are done is misleading; two models can only be compared at the same n,
and in absolute passed-task counts (at small n, one task is worth 5-6 percentage points).
`partial_credit` is the more stable signal.

## Data

| File | What |
| --- | --- |
| `data/tasks_all.csv` | one row per (model, task): score, passed, assertion counts, tokens, tool calls, steps, latency |
| `data/{base,opera,gemma}_ab600.slim.json` | full per-task records incl. per-assertion pass/fail, minus conversation traces |
| `data/manifest.json` | run metadata, summaries, per-assertion-type totals per model |

Full records including every message of every trajectory (~350 MB gzipped) live on
[Hugging Face](https://huggingface.co/datasets/beyoru/automationbench600-open-weight-runs) —
too large for git.

Reproduce the tables:

```bash
python scripts/analyze.py data
```

## Serving setup

See [RUNBOOK.md](RUNBOOK.md) for the exact SGLang commands, the tp sizes, the Gemma 4 thinking
patch, and four configuration traps that silently zero out or 20×-slow a run.
