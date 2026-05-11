# grove

**Local-first AI toolkit.** Modular components for projects that want semantic search, structured project management, and a swarm of local models — without cloud dependencies or per-token costs.

Grove emerged from [grow](https://github.com/michaelkalish2008/grow), a local semantic search and brand-building system. The infrastructure proved useful enough to extract. Each module works independently; all three compose into a complete local-first AI stack.

---

## Modules

| Module | What it gives you | Dependencies |
|--------|-------------------|--------------|
| `grove[board]` | SQLite-backed agile board — epics, stories, sprints, learnings, standups | none (stdlib only) |
| `grove[swarm]` | Local Ollama worker pool + Claude orchestrator with judge scoring | `anthropic` |
| `grove[index]` | Corpus index — files, chunks, tag taxonomy, FAISS embeddings, clustering | `faiss-cpu`, `sentence-transformers` |
| `grove[all]`   | Everything above | all of the above |

---

## Install

```bash
# Board only — zero heavy dependencies
pip install grove[board]

# Swarm (requires Ollama running locally)
pip install grove[swarm]

# Full stack
pip install grove[all]
```

---

## Quickstart

### grove[board] — Agile board in any project

```bash
# Initialize a board in your project
grove init --db data/grove.db --modules board

# Or in Python
import grove
conn = grove.init("data/grove.db", modules=["board"])
```

Then use the CLI scripts directly:

```bash
# Create a story
python -m grove.board.scripts.add_story \
  --epic foundation --title "Set up CI" --points 2 --sprint

# Update status
python -m grove.board.scripts.update_story --id 1 --status in-progress

# Validate board integrity
python -m grove.board.scripts.validate_board

# Close the sprint
python -m grove.board.scripts.close_sprint

# Start next sprint
python -m grove.board.scripts.start_sprint --name S02 --goal "Ship index module"
```

If you use [Claude Desktop with Cowork](https://claude.ai), install the skill layer:

```bash
bash grove/board/install.sh   # adds /board:run, /board:update, /board:retro, /board:grill-me
```

#### Board schema

Four tables form the core:

```
epics       — top-level work themes (slug, title, priority)
stories     — units of work (title, points, status, refs, branch)
sprints     — time-boxes (name, goal, start/end date, velocity)
learnings   — captured insights (category, title, body, sprint_id)
```

All board mutations go through scripts — no ad hoc SQL. The scripts handle `completed_at`, constraint checks, and sprint assignment atomically.

---

### grove[swarm] — Local model swarm

Requires [Ollama](https://ollama.ai) running locally with at least one model pulled:

```bash
ollama pull qwen3:8b
```

```python
from grove.swarm import WorkerPool, OrchestratorConfig, Orchestrator

# Run a task across a pool of local workers
pool = WorkerPool(model="qwen3:8b", size=3)
pool.warm()  # verifies Ollama is reachable

results = pool.map_sync(
    subtasks=["Summarize section 1", "Extract key terms from section 2"],
    context="...your document text...",
)
for r in results:
    print(f"Worker {r.worker_id}: {r.answer}")
```

For Claude-orchestrated map-reduce (plan → local workers → synthesize):

```python
from grove.swarm import Orchestrator, OrchestratorConfig

orch = Orchestrator(OrchestratorConfig(
    model="qwen3:8b",
    pool_size=3,
    sampling_rate=0.5,          # 50% of results scored by Claude judge
    judge_db_path="data/grove.db",  # persist scores (optional)
))
orch.warm()

result = orch.run_sync(
    task="Analyze the tradeoffs of this system design",
    context="...your context...",
)
print(result.answer)
print(f"Judge score: {result.avg_score:.1f}/10")
```

#### How the swarm works

```
Claude (plan)
    ↓  decompose task into subtasks
[worker 0] [worker 1] [worker 2]   ← local Ollama models, parallel
    ↓  results
Sampling layer (rate/reservoir/stratified)
    ↓  sampled subset
Claude (judge)  ← scores accuracy, conciseness, hallucination risk, tone, style
    ↓  scores persisted to grove.db
Claude (synthesize)  ← final answer from all worker results
```

Local models handle grunt work. Claude handles planning, judgment, and synthesis. The sampling layer controls cost — you score a fraction of outputs, not all of them.

---

### grove[index] — Corpus index *(coming in S02)*

SQLite + FAISS + tag taxonomy with descriptive statistics and auto-management.

The key insight: **tags reduce the search space before embeddings are queried.** Instead of brute-force vector search over a full corpus, the tag layer pre-partitions by topic. Local encoders and LLMs operate on already-filtered subsets — which makes them viable where full-corpus search would require something much heavier.

Tag auto-management (consolidation, splitting, drift detection) keeps the taxonomy accurate as the corpus grows.

```python
# Preview — API stabilizing in S02
from grove.index import CorpusIndex

idx = CorpusIndex("data/grove.db")
idx.ingest("path/to/repo/")         # chunk, hash-check, tag, embed
results = idx.search("ReAct agents", top_k=10, tags=["local-ai"])
```

---

## Project structure

```
grove/
  grove/
    __init__.py        # grove.init(), grove.modules()
    cli.py             # grove init / status / modules
    board/
      scripts/         # add_story, update_story, close_sprint, ...
      skills/          # Cowork SKILL.md files
    swarm/
      ollama_client.py
      local_react_agent.py
      worker_pool.py
      sampling_layer.py
      claude_ops.py
      claude_judge.py
      orchestrator.py
    index/             # coming S02
  schema/
    agile/agile.sql    # board tables
    swarm/swarm.sql    # judge_scores table
    corpus/            # coming S02
    taxonomy/          # coming S02
    learnings/         # coming S02
  tests/
```

---

## Design principles

**Agnostic.** Grove doesn't know what your project does. `grove init` creates a database; you decide what goes in it. Scripts take `--db` flags; `GROVE_DB` env var overrides the default path.

**Modular.** Install one module, all modules, or none. No module requires another at the Python level. If you want persistence from swarm scores, you wire it yourself — grove doesn't assume you have an index.

**Local-first.** The only required external service is Ollama (for swarm). Everything else is SQLite and stdlib. No SaaS backends, no API keys required for board or index modules.

**Extensible.** The schema module registry (`grove_modules` table) tracks what's installed. Add your own tables by applying additional SQL files — grove doesn't own the database.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROVE_DB` | `data/grove.db` | Override database path |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TIMEOUT` | `120` | Generation timeout (seconds) |
| `OLLAMA_TAG_MODEL` | `qwen3:8b` | Model used for tag extraction (index module) |
| `CLAUDE_OPS_MODEL` | `claude-3-5-haiku-20241022` | Claude model for plan + synthesize |
| `CLAUDE_JUDGE_MODEL` | `claude-3-5-haiku-20241022` | Claude model for scoring |
| `ANTHROPIC_API_KEY` | *(required for swarm)* | Anthropic API key |

---

## Origin

Grove was extracted from [grow](https://github.com/michaelkalish2008/grow) — a local-first semantic search and content infrastructure system. The board, swarm, and index modules were built to manage grow's own development before being generalized here.

---

## License

MIT
