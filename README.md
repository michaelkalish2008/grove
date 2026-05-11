# grove

> **Infrastructure for empowering Claude.** Grove gives Claude the organizational memory, engineered context layer, and local model workforce it needs to operate efficiently at scale — without the cost and latency growing with the corpus.

---

## Before and after

**Without grove:**
Claude starts every session blind. You paste files into the context window. It re-reads everything it already understood last time. It forgets what it decided, what it learned, and why it made the tradeoffs it did. At 10,000 files, the context window runs out before the relevant signal arrives.

**With grove:**
Claude reads its own board — three stories in-progress, one blocker, a learning logged two sessions ago that's directly relevant. It queries a pre-filtered, narratively summarized subspace of the corpus, not the full index. Local models handle keyword extraction, tagging, and summarization. Claude handles planning, judgment, and synthesis. Every decision is written to SQLite. Every session starts informed.

---

## The problem with scaling AI-assisted work

Claude is powerful. But raw capability doesn't solve the scaling problem: as your codebase, knowledge base, or document corpus grows, the cost and latency of giving Claude useful context grows with it. Naive approaches — dumping files into the context window, embedding everything, running full semantic search on every query — work at small scale and break at large scale.

The deeper issue is that Claude has no organizational infrastructure of its own. It can't remember what it decided last sprint, track what it learned from a bug fix, or know which 200 files out of 10,000 are actually relevant to the task at hand. Every session starts blind.

Grove solves both problems.

---

## Who this is for

Grove is for engineers and researchers who use Claude as a core part of how they work — and who have hit the ceiling of naive context management.

You're likely here if:
- Your project has grown past the point where pasting files into context works reliably
- You want Claude to carry knowledge forward across sessions, not re-derive it every time
- You're running repeated, parallelizable tasks (tagging, summarizing, extracting) that don't need Claude-level capability but do need to be accurate
- You want visibility into what Claude is doing, what it decided, and how well it's performing — not just outputs
- You want a system that gets smarter as your corpus grows, not one that degrades

---

## What grove does

Grove gives Claude three things it doesn't have by default:

### 1. Organizational memory (`grove[board]`)

A structured agile board — epics, stories, sprints, learnings, standups — persisted in SQLite and managed through canonical scripts. Claude uses the board to track its own work, carry forward decisions across sessions, and log learnings the moment they occur rather than losing them to context loss.

This is not a project management tool bolted onto Claude. It's Claude's own working memory, written in a format Claude can read, query, and update autonomously.

**The learnings system is what makes this more than task tracking.** Every time Claude fixes a bug and understands the root cause, makes an architectural decision, or identifies a process failure, it writes a structured learning: category, title, body, sprint. Nightly embedding and weekly consolidation deduplicate and surface patterns across sessions. The result is a knowledge base that grows with the project — not a chat history that scrolls away.

When Claude starts a session, it reads recent learnings relevant to the current story before touching any code. It doesn't rediscover what it already knows.

### 2. An engineered context layer (`grove[index]`)

The central technical contribution of grove is a corpus indexing system that combines five complementary representations into a search space that is semantically rich, statistically grounded, and self-maintaining — without the brittleness of knowledge graphs or the opacity of pure vector retrieval.

**Semantic embeddings** (via `sentence-transformers`) encode the meaning of each chunk as a dense vector. FAISS retrieves the nearest neighbors to a query at sub-millisecond latency, regardless of corpus size. This is the retrieval backbone — fast and meaning-aware, but on its own, uninterpretable.

**A tag taxonomy** extracts discrete, human-readable concepts from each chunk using a local LLM (grove[swarm]). Tags form a sparse, interpretable index over the corpus. Unlike embeddings, they can be inspected, merged, and reasoned about directly. A chunk tagged `[local-ai, react-loop, ollama]` is immediately legible — to Claude and to you.

**Descriptive statistics** track term frequency, co-occurrence, and correlation across the entire corpus. These statistics power automatic tag management: consolidating near-synonyms, splitting overloaded tags, detecting drift as the corpus evolves. The taxonomy is not a static list you maintain — it's a living structure the system keeps accurate.

**Clustering** (HDBSCAN + UMAP 3D projection) operates on the embedding space to discover emergent regions of semantic density. Where descriptive statistics reveal *what* the corpus talks about, clustering reveals *how it's organized* — surfacing natural groupings that no predefined schema could anticipate. Clusters are computed, not declared.

**Narrative summaries** are the layer that makes the rest usable at query time. Each cluster — and any filtered subspace defined by tag intersection — can be summarized into a deterministic natural-language narrative using local models (grove[swarm]). Because the summary procedure is deterministic and the cluster membership is stable between re-indexing runs, narratives can be cached and retrieved rather than re-generated on every query.

This determinism is the key property. It means: when Claude needs to understand what a region of the corpus contains, it reads a pre-computed narrative rather than scanning raw chunks. The search problem transforms from *find similar text* into *find the region of meaning that contains the answer* — then read the narrative that describes it.

The combination replaces brittle features typical of knowledge graphs (explicitly declared edges, fragile under schema change) and hierarchical labeling systems (every node manually placed, taxonomy drift undetected) with a structure that emerges statistically from the corpus itself. Tags reduce the semantic search space before FAISS is queried. Clustering organizes what the tags reveal. Narratives make clusters legible to Claude without burning context on raw chunks.

**Tags reduce the search space. Clusters organize it. Narratives make it readable.**

As the corpus grows, the system gets *more* accurate, not less — because the statistical signal strengthens, the clusters tighten, and the narratives become more precise.

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

## Why not LangChain / LlamaIndex / a RAG framework?

Standard RAG frameworks solve retrieval. Grove solves *context engineering at scale* — a broader problem of which retrieval is one part.

| | Standard RAG | Grove |
|--|-------------|-------|
| **Retrieval** | Vector similarity over full corpus | Tag pre-filter → FAISS over subspace |
| **Search space** | Flat — all chunks equally eligible | Structured — clusters with narrative summaries |
| **Taxonomy** | Static (you define it) or absent | Emergent — statistically derived, auto-managed |
| **Agent memory** | Per-session (lost on close) | Persistent — SQLite board + learnings across sessions |
| **Volume work** | Claude (expensive) or no LLM | Local Ollama workers (cheap, parallel) |
| **Quality visibility** | None | Judge scoring by dimension + prompt versioning |
| **Knowledge capture** | None | Structured learnings with nightly deduplication |

Knowledge graphs and hierarchical ontologies offer interpretability but require manual curation and break under schema change. Grove's tag taxonomy is interpretable *and* self-maintaining — because it's statistically derived from the corpus rather than declared. Clusters and narratives provide the structure of an ontology without its fragility.

---

## Design principles

**Claude-first.** Every module is designed around Claude's working patterns — not as a tool Claude uses, but as infrastructure Claude inhabits. The board is Claude's memory. The index is Claude's perception layer. The swarm is Claude's workforce.

**Agnostic.** Grove doesn't know what your project does. `grove init` creates a database; you decide what goes in it. No module assumes another is present.

**Local-first.** No SaaS backends. No per-token costs for indexing or tagging. The only cloud dependency is the Anthropic API — used only for planning, synthesis, and judgment, not for volume work.

**Statistically grounded.** The tag taxonomy is not a static list. Term frequency, co-occurrence, and correlation statistics drive automated decisions about when to consolidate, split, or retire tags. The system learns the structure of your corpus rather than requiring you to define it upfront.

**Observable.** Everything grove does is written to SQLite in structured form. No opaque embeddings without corresponding metadata. No agent decisions without a standup record. No quality signal without a persisted score.

---

## Origin

Grove was extracted from [grow](https://github.com/michaelkalish2008/grow) — a local-first semantic search and brand-building system. Grow uses grove to manage its own development: the board tracks grow's stories and sprints, the swarm runs grow's tagging pipeline, and the index organizes grow's corpus of code, content drafts, and research notes.

This is not incidental. Grove was designed by being used — the abstractions reflect real friction encountered while building a production corpus indexing system, not hypothetical use cases. The learnings system exists because Claude kept re-deriving the same root causes. The sampling layer exists because judging every worker output was immediately cost-prohibitive. The tag auto-management exists because manually curating a taxonomy at 10,000 chunks doesn't scale.

Grow is the reference implementation. If you want to see all three modules working together in a real project, start there.

---

## License

MIT
