# grove

> **Infrastructure for empowering Claude.** Grove gives Claude the organizational abilities, contextual awareness, and local workforce it needs to engineer its own context — efficiently, scalably, and at a cost that doesn't grow with the corpus.

---

## The problem with scaling AI-assisted work

Claude is powerful. But raw capability doesn't solve the scaling problem: as your codebase, knowledge base, or document corpus grows, the cost and latency of giving Claude useful context grows with it. Naive approaches — dumping files into the context window, embedding everything, running full semantic search on every query — work at small scale and break at large scale.

The deeper issue is that Claude has no organizational infrastructure of its own. It can't remember what it decided last sprint, track what it learned from a bug fix, or know which 200 files out of 10,000 are actually relevant to the task at hand. Every session starts blind.

Grove solves both problems.

---

## What grove does

Grove gives Claude three things it doesn't have by default:

### 1. Organizational memory (`grove[board]`)

A structured agile board — epics, stories, sprints, learnings, standups — persisted in SQLite and managed through canonical scripts. Claude uses the board to track its own work, carry forward decisions across sessions, and log learnings the moment they occur rather than losing them to context loss.

This is not a project management tool bolted onto Claude. It's Claude's own working memory, written in a format Claude can read, query, and update autonomously.

### 2. An engineered context layer (`grove[index]`)

The central technical contribution of grove is a corpus indexing system that combines three complementary representations:

**Semantic embeddings** (via `sentence-transformers`) encode the meaning of each chunk as a dense vector. FAISS retrieves the nearest neighbors to a query at sub-millisecond latency, regardless of corpus size.

**A tag taxonomy** extracts discrete, human-readable concepts from each chunk using a local LLM (Ollama). Tags form a sparse, interpretable index over the corpus. Unlike embeddings, they can be inspected, merged, and reasoned about directly.

**Descriptive statistics** track term frequency, co-occurrence, and correlation across the corpus. These statistics power automatic tag management: consolidating near-synonyms, splitting overloaded tags, detecting taxonomic drift as the corpus evolves.

The combination is the key insight: **tags reduce the semantic search space before embeddings are queried.** A query tagged `[local-ai, architecture]` searches a pre-filtered subset of the corpus, not the full index. Local encoders and LLMs operate on high-signal subsets — which makes them viable at scales where full-corpus search would require something far more expensive.

As the corpus grows, the system gets *more* accurate, not less. Clustering algorithms (HDBSCAN, UMAP) reveal emergent structure in the tag space, driving the auto-management layer that keeps the taxonomy clean without manual curation.

### 3. A local model workforce (`grove[swarm]`)

Claude is expensive and rate-limited. Grunt work — keyword extraction, chunk tagging, summarization, structured extraction — doesn't require Claude. It requires *good enough, fast, and cheap*.

Grove's swarm module deploys a pool of local Ollama models (qwen3, gemma, llama) as parallel workers running a ReAct loop. Claude handles the two things that actually require it: **planning** (decomposing tasks into parallelizable subtasks) and **judgment** (orchestrating, synthesizing, and scoring outputs).

A sampling layer (rate-based, reservoir, or stratified) controls which worker outputs get routed to Claude's judge — so you get performance visibility without paying for every exchange. Judge scores are versioned by prompt, enabling attribution of quality changes to specific prompt edits over time.

```
Claude (plan)       ← decomposes task into parallelizable subtasks
    ↓
[worker] [worker] [worker]   ← local Ollama models, parallel ReAct loops
    ↓
Sampling layer      ← rate/reservoir/stratified: controls judge cost
    ↓
Claude (judge)      ← scores accuracy, conciseness, hallucination risk, tone, style
    ↓
Claude (synthesize) ← produces final answer from all worker outputs
```

The result: Claude's intelligence is applied where it compounds. Local models absorb the volume. Cost scales with judgment, not with throughput.

---

## Visibility and performance insights

Grove is not a black box. Every decision Claude makes — what story to work on, what it learned, how well the local workers performed — is written to SQLite in structured, queryable form.

- **Board dashboard**: live view of sprint progress, story status, velocity trends, and captured learnings
- **Judge scoring**: per-worker, per-prompt-version scores across five quality dimensions — accuracy, conciseness, hallucination risk, tone, style match
- **Tag statistics**: term frequency, co-occurrence, and correlation visible in the index — you can see exactly what the corpus knows and where the taxonomy is drifting
- **Standup log**: every session writes a structured record of what was done, what's next, and what's blocking — readable by Claude and by you

---

## Abstracted interaction

Grove compresses complex multi-step workflows into single commands:

| Command | What it does |
|---------|-------------|
| `/board:run` | Cold-start: reads the board, surfaces last standup + learnings, validates refs, picks up in-progress work |
| `/board:update <task>` | Jumps to a specific story, sprint action, or free-form task |
| `/board:retro` | Sprint retrospective — velocity, completion rate, learnings delta, honest feedback, sprint close |
| `/board:grill-me` | Relentless depth-first interview on a plan or design — resolves the decision tree before code is written |

These aren't wrappers around Claude prompts. They're encoded workflows that read the database, validate state, execute scripts, and write structured records — all in a single invocation.

---

## Modules

| Module | Role | Dependencies |
|--------|------|--------------|
| `grove[board]` | Claude's organizational memory — agile board, learnings, standups | none (stdlib + SQLite) |
| `grove[index]` | Engineered context layer — semantic embeddings, tag taxonomy, descriptive statistics, clustering | `faiss-cpu`, `sentence-transformers` |
| `grove[swarm]` | Local model workforce — ReAct worker pool, Claude orchestrator, judge scoring | `anthropic` |
| `grove[all]` | Full stack | all of the above |

Each module works independently. All three compose into a system where Claude manages its own context, deploys local workers for scale, and surfaces everything it does to the user.

---

## Install

```bash
# Board only — zero dependencies beyond Python + SQLite
pip install grove[board]

# Full stack (requires Ollama + Anthropic API key)
pip install grove[all]
```

Requirements files for each module:

```bash
pip install -r requirements-board.txt    # agile board, no heavy deps
pip install -r requirements-swarm.txt    # local model swarm
pip install -r requirements-index.txt    # corpus index + encoder
```

---

## Quickstart

### Board

```bash
grove init --db data/grove.db --modules board

# Create a story
python -m grove.board.scripts.add_story \
  --epic foundation --title "Set up CI" --points 2 --sprint

# Update status
python -m grove.board.scripts.update_story --id 1 --status in-progress

# Validate board integrity
python -m grove.board.scripts.validate_board
```

Install Cowork skills for Claude Desktop:

```bash
bash grove/board/install.sh
# Adds: /board:run  /board:update  /board:retro  /board:grill-me  /board:init
```

### Swarm

```bash
ollama pull qwen3:8b   # or gemma4, llama3.2, any Ollama model
```

```python
from grove.swarm import Orchestrator, OrchestratorConfig

orch = Orchestrator(OrchestratorConfig(
    model="qwen3:8b",
    pool_size=3,
    sampling_rate=0.5,             # score 50% of outputs via Claude judge
    judge_db_path="data/grove.db", # persist scores for trend analysis
))
orch.warm()

result = orch.run_sync(
    task="Summarize the key architectural decisions in this codebase",
    context="...your context...",
)
print(result.answer)
print(f"Judge avg: {result.avg_score:.1f}/10  |  {result.elapsed_s:.1f}s")
```

### Index *(S02 — coming soon)*

```python
from grove.index import CorpusIndex

idx = CorpusIndex("data/grove.db")
idx.ingest("path/to/repo/")   # chunk → hash-check → tag (Ollama) → embed (sentence-transformers)
results = idx.search("ReAct agent architecture", top_k=10, tags=["local-ai"])
```

---

## Project structure

```
grove/
  grove/
    __init__.py        # grove.init(), grove.modules()
    cli.py             # grove init / status / modules
    board/
      scripts/         # add_story, update_story, close_sprint, validate_board, ...
      skills/          # Cowork SKILL.md files (/board:run, :update, :retro, :grill-me)
      install.sh       # installs Cowork skills into Claude Desktop
    swarm/
      ollama_client.py        # Ollama REST wrapper (sync + async)
      local_react_agent.py    # stateless ReAct loop over Ollama
      worker_pool.py          # pre-warmed agent pool, asyncio dispatch
      sampling_layer.py       # rate/reservoir/stratified sampling gate
      claude_ops.py           # claude_plan() + claude_synthesize() with prompt caching
      claude_judge.py         # 5-dimension scoring, prompt versioning
      orchestrator.py         # plan → map → sample → judge → synthesize
    index/             # S02
  schema/
    agile/agile.sql    # board tables: epics, stories, sprints, learnings, standups
    swarm/swarm.sql    # judge_scores table
    corpus/            # S02: files, chunks, file_terms, chunk_terms
    taxonomy/          # S02: terms, term_stats, term_correlations, term_narratives
    learnings/         # S02: learnings with embedding support
  tests/
    board/             # 15 passing tests — schema, CRUD, validate_board
    swarm/             # S02
```

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROVE_DB` | `data/grove.db` | Path to grove database |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TIMEOUT` | `120` | Generation timeout in seconds |
| `OLLAMA_TAG_MODEL` | `qwen3:8b` | Local model for tag extraction |
| `GROVE_ENCODER_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model for chunk embeddings |
| `SENTENCE_TRANSFORMERS_HOME` | `~/.cache/torch/sentence_transformers` | Local encoder model cache |
| `CLAUDE_OPS_MODEL` | `claude-3-5-haiku-20241022` | Claude model for plan + synthesize |
| `CLAUDE_JUDGE_MODEL` | `claude-3-5-haiku-20241022` | Claude model for output scoring |
| `ANTHROPIC_API_KEY` | *(required for swarm)* | Anthropic API key |

---

## Design principles

**Claude-first.** Every module is designed around Claude's working patterns — not as a tool Claude uses, but as infrastructure Claude inhabits. The board is Claude's memory. The index is Claude's perception layer. The swarm is Claude's workforce.

**Agnostic.** Grove doesn't know what your project does. `grove init` creates a database; you decide what goes in it. No module assumes another is present.

**Local-first.** No SaaS backends. No per-token costs for indexing or tagging. The only cloud dependency is the Anthropic API — used only for planning, synthesis, and judgment, not for volume work.

**Statistically grounded.** The tag taxonomy is not a static list. Term frequency, co-occurrence, and correlation statistics drive automated decisions about when to consolidate, split, or retire tags. The system learns the structure of your corpus rather than requiring you to define it upfront.

**Observable.** Everything grove does is written to SQLite in structured form. No opaque embeddings without corresponding metadata. No agent decisions without a standup record. No quality signal without a persisted score.

---

## Origin

Grove was extracted from [grow](https://github.com/michaelkalish2008/grow) — a local-first semantic search and brand-building system built to manage its own development using the same infrastructure it provides. The board, swarm, and index modules were battle-tested in grow before being generalized here.

---

## License

MIT
