# SWE-Pocket: A Size-Stratified Evaluation Resource for Local Coding Agents

## Abstract

Coding agents are evaluated almost exclusively on large, cloud-scale benchmarks,
while the fastest-moving frontier is agents small enough to run on a developer's
own machine. Yet no standard benchmark reports repository size as a variable:
size is fixed by construction and never measured. We introduce SWE-Pocket, a
size-stratified evaluation resource for Python repositories. It combines the 129
task instances released with the competition — each with a problem statement, a
gold patch, and a test patch, and each traced to a merged upstream pull request —
with 24 tasks we mine from four deliberately compact libraries under an identical
schema. Analysing the code graphs of all 153 tasks, we show first that repository
size is not one axis but three — breadth, coupling, and depth — and that these
axes disagree, so stratifying on node count alone misranks repositories. We then
show these structural axes are largely independent of the fix a task requires:
across the 129 provided tasks, gold-patch churn correlates with node count at
r = −0.01, and 71% of tasks touch a single source file with a median fix of 13
changed lines. We release our mined tasks, construction and analysis tooling,
generated graphs, and derived metrics; competition-provided data are referenced,
never redistributed.

---

## 1. Introduction

The Gemma 4 Developer Agent competition exists because the frontier of practical
coding agents is moving toward models small enough to run on consumer hardware —
laptops, single GPUs, offline machines. Evaluation has not followed. The standard
suite for measuring a coding agent, from SWE-bench to its many descendants, fixes
its repository set to a handful of large, heavily depended-on projects and
reports a single number: resolve rate. Repository size is not a variable in these
benchmarks; it is a constant so large that every task inherits the same
cloud-scale context cost.

This leaves a concrete, unanswered question for anyone building the agents this
competition is about. If two tasks require the same one-line edit, does it matter
whether that line lives in a 75-node library or a 4,000-node framework? Every
existing benchmark would score them identically, because none reports the
structure the agent had to navigate. The gap is not that small agents perform
worse; it is that **no benchmark makes repository size a controlled, reported
axis at all.**

We introduce SWE-Pocket, a size-stratified evaluation resource that closes this
gap without requiring any model training or GPU to construct or analyse. Our
contributions are three:

1. **A size-stratified resource.** 153 Python task instances across two strata:
   129 provided by the competition across four large libraries, and 24 we mine
   from four compact libraries, all sharing one schema (problem statement, gold
   patch, test patch) and one measurement pipeline (§3).

2. **An empirical finding about size itself.** Repository size decomposes into
   three axes — *breadth* (nodes/files), *coupling* (edges per node, fan-in), and
   *depth* (longest call chain) — that rank repositories differently, and none of
   them predicts the fix a task requires. Stratifying on node count, the obvious
   proxy, misranks repositories on the other two axes (§4.2–4.3).

3. **A reusable, GPU-free construction and analysis pipeline.** Every number in
   this paper is recomputed by a public notebook from released tables, and the
   tables themselves are rebuilt from the competition data by released scripts,
   on a laptop CPU (§4).

We make no claim about agent accuracy. We cut model baselines deliberately: with
limited time, we chose to release a correct, fully reproducible resource and
analysis rather than an under-powered leaderboard. §5 states this limit plainly.

---

## 2. Related Work

**SWE benchmarks fix their repositories.** SWE-bench [1] draws its tasks from
twelve large Python repositories and reports resolve rate; SWE-bench Verified [2]
is a human-validated subset of the same; SWE-bench Multimodal [3] extends to
visual tasks but not to size; SWE-bench-Live [4] keeps tasks fresh, but
repository scale is unchanged. In all of them, repository size is a fixed
property of the source projects, never an analysis variable.

**Repo-level agent methods.** Agentless [5], AutoCodeRover [6], SWE-agent [7],
and OpenHands [8] differ in how they localise and edit, but each is evaluated on
the same fixed-size corpora. Their comparisons answer "which method resolves more
tasks," not "how does repository scale change what a method must do."

**Code-graph and retrieval methods.** RepoGraph [9], LocAgent [10], and
GraphRAG-style systems [11] exploit structure for navigation — precisely the
structure SWE-Pocket measures. They consume graphs as a tool; we treat the graph
as the object of study, to make size reportable independently of success.

**Small and local models.** Open code models such as Qwen2.5-Coder [14],
DeepSeek-Coder [15], and StarCoder2 [16] are the agent class this resource is
for. Their agentic evaluation, too, defaults to the large SWE-bench corpora.

**Benchmark critique.** A growing literature asks what SWE-bench actually
measures: solution leakage and weak tests [12], patches that pass tests without
being correct [13], and memorisation of benchmark repositories [17]. Concurrent
entries to this competition likewise audit its own benchmark, for example for
run-to-run noise. We share the spirit of "measure the benchmark, not just the
agent," but along an axis none of these examine.

**Gap statement.** All of the work above fixes repository size and reports
success. None stratifies by size or reports the structure an agent navigated.
That is the gap SWE-Pocket fills.

---

## 3. The SWE-Pocket Resource

### 3.1 The large stratum (provided)

The competition ships `tasks.jsonl`, 129 task definitions across four Python
libraries: `fastapi` (67), `rich` (48), `psf/requests` (13), and `httpx` (1).
Each row contains an `instance_id`, a `repo`, a `base_commit`, a gold `patch`, a
`test_patch`, and a `problem_statement`. We verified provenance for all 129
through the GitHub API: every `instance_id` corresponds to a real, **merged**
upstream pull request, and every `base_commit` equals that pull request's base
SHA. None of the 129 base commits appear among SWE-bench's 2,294 instances, so
these are not a relabelled public set.

The competition also provides, per unique base commit (127 of them; two base
commits are shared by two tasks each), a code graph and a 256-dimensional node
embedding. We use the graphs for structural measurement (§3.3). Graph node text
is a stubbed signature rendering — function bodies are replaced with `...` — so
the graphs are a navigation aid, not a recoverable task source.

### 3.2 The compact stratum (mined)

To make repository size a genuine variable rather than a constant, we mined a
compact stratum. `mine_compact.py` pulls merged pull requests from four
deliberately small, dependency-light libraries — `pypa/packaging`,
`jazzband/prettytable`, `davidhalter/parso`, and `theskumar/python-dotenv` — and
keeps those whose diff touches at most 6 files and between 4 and 160 lines, with
both a source change and a test change. The result is 24 tasks, six per
repository, in exactly the schema of the provided 129. `build_compact_graphs.py`
then parses each repository at its base commit with Python's `ast` and emits a
call graph in the provided schema (nodes keyed `module.symbol`, `calls` edges
between uniquely resolved symbols), so the compact stratum runs through
identical measurement code. The 24 tasks resolve to 22 unique base commits.

The strata are cleanly separated: compact repositories span 75–606 nodes, the
large stratum 711–4,597. That separation is what lets us treat size as a
controlled axis.

### 3.3 Measurement

For every task we compute, from its code graph alone: node count, edge count,
file count, density (edges per node), the fraction of isolated nodes, maximum
fan-in, and `max_depth`, the longest acyclic call chain (computed with a
cycle-safe iterative traversal, since naive recursion does not scale to
multi-thousand-node graphs). From the task definition we compute two independent
signals: gold-patch churn (added + deleted lines) as a proxy for fix size, and
the FAIL_TO_PASS test count recovered from `test_patch`. In the large stratum,
106 of 129 tasks expose at least one FAIL_TO_PASS test; in total we recover 464
FAIL_TO_PASS and 124 PASS_TO_PASS test functions.

---

## 4. Structural Analysis

### 4.1 Setup

We analyse all 153 tasks; there is no sampling. Metrics are reported per
repository as means (churn as a median); pooled correlations use the 129 large
tasks, the only stratum large enough for per-instance inference.

### 4.2 Result 1 — repository size is three axes

**Table 1. Repository structure by stratum (means; churn is median lines).**

| repo | stratum | n | nodes | edges | density | isolated | max depth | gold churn |
|---|---|---|---|---|---|---|---|---|
| `fastapi` | large | 67 | 3,968 | 2,458 | 0.62 | 0.69 | 57 | 19 |
| `rich` | large | 48 | 1,970 | 5,626 | 2.86 | 0.04 | 172 | 10 |
| `requests` | large | 13 | 733 | 1,819 | 2.48 | 0.08 | 53 | 5 |
| `httpx` | large | 1 | 740 | 1,618 | 2.19 | 0.03 | 33 | 86 |
| `packaging` | compact | 6 | 579 | 569 | 0.98 | 0.57 | 9 | 12 |
| `parso` | compact | 6 | 604 | 232 | 0.38 | 0.76 | 5 | 6 |
| `prettytable` | compact | 6 | 215 | 29 | 0.14 | 0.68 | 2 | 12 |
| `python-dotenv` | compact | 6 | 75 | 82 | 1.08 | 0.41 | 6 | 19 |

![Figure 1](fig1_three_axes.png)

**Figure 1.** Each repository on the three axes, rows ordered by node count.
Dots are tasks; ticks are repository means. If size were one axis, the row order
would hold across all three panels. It does not.

Table 1 and Figure 1 separate three things a single number conflates.

- **Breadth.** `fastapi` is the largest by node count, but its graph is
  fragmented: 69% of its nodes have no incoming or outgoing call, the highest of
  any large repository. Raw volume overstates how much structure an agent must
  navigate to reach a given definition.
- **Coupling.** `rich` is half the size of `fastapi` yet has 2.3× the call edges
  and 4.6× the density, with a single hotspot (its `Console` class) receiving a
  mean maximum fan-in of 359 calls. Narrow but heavily entangled.
- **Depth.** `rich`'s longest call chain averages 172 frames versus 57 for
  `fastapi` and 33 for `httpx`. An agent reasoning top-down from an entry point
  traverses roughly three times more frames on `rich` to reach a leaf.

The compact stratum shows the same disagreement an order of magnitude lower.
`packaging` (579 nodes) and `parso` (604) are nearly equal in breadth but differ
2.6× in density and nearly 2× in depth. Most strikingly, `python-dotenv` — the
smallest repository in the resource at 75 nodes — is *more* densely coupled than
`fastapi`, the largest, at 3,968.

**The finding:** a benchmark stratifying on node count alone would rank `fastapi`
as the hardest repository to navigate and `rich` as intermediate, when by
coupling and depth `rich` is the harder one and `fastapi`'s extra nodes are
largely inert. Size must be reported as three axes, not one.

### 4.3 Result 2 — structure is largely independent of fix size

If the structural axes tracked fix size, they would be redundant — one could
stratify on churn instead. They do not.

**Table 2. Correlation of structural axes with gold-patch churn (n = 129).**

| axis | Pearson r with churn |
|---|---|
| nodes | −0.014 |
| edges | +0.088 |
| density | +0.055 |
| max depth | +0.102 |

All four are effectively zero. The typical task is also small: **91 of 129 tasks
(71%) touch exactly one source file**, and the median fix is **13 changed lines**
(7 within the single-file subset). Fix size and structural size are close to
orthogonal.

We report this carefully. A handful of outliers (one `rich` task changes 12,740
lines across 26 files) inflate variance, and within the single-file subset the
node–churn correlation rises to r = +0.20. Structure carries a weak signal about
fix size, not none. The defensible claim is the one the data support: a
benchmark can hold fix size roughly constant — most tasks are single-file,
small-edit fixes — while repository scale varies by more than an order of
magnitude. No existing benchmark exploits this; they let both vary together and
report neither.

### 4.4 Result 3 — the pipeline generalises

Applying the identical pipeline to the 24 mined compact tasks reproduces the
same axis disagreement (Table 1, lower block; Figure 1, orange) with no
repository-specific tuning. SWE-Pocket is therefore a *construction*, not a
one-off analysis of the provided data: the same schema, graph builder, and
metrics extend to any repository a maintainer chooses.

### 4.5 Threats to validity

We make claims about structure, not agents. (i) The structural metrics are a
*proxy* for navigation cost; we did not measure agent behaviour, so we cannot
say how much harder navigation is, only that the axes separate. (ii) Compact
graphs are built by our `ast` builder, provided graphs by the organisers'; the
builders may resolve calls differently, so cross-stratum comparisons of edge
counts carry this caveat, while within-stratum comparisons do not. (iii) The
resource is Python-only. (iv) The compact stratum is small (24 tasks), so its
statistics are descriptive, not inferential. (v) Gold-patch churn proxies fix
*size*, not fix *difficulty*. (vi) We report no model baselines (§5).

---

## 5. Discussion and Limitations

**What reporting size as three axes buys.** A resource like this one can now pose
questions a resolve-rate number cannot. Does a fixed one-line edit get harder as
coupling rises, independent of node count? Does depth, not breadth, decide where
a small-context agent loses the thread? These questions are falsifiable and cheap
to test once structure is reported. We leave them as future work and release the
resource that makes them askable.

**What we do not claim.** We report no agent accuracy and no failure taxonomy.
An earlier plan included model baselines and a failure analysis; with a fixed
time budget we cut both rather than ship an under-powered leaderboard whose
numbers would not be trustworthy. We state this so no reader mistakes the absence
of a baseline table for an oversight.

**Honesty about the correlation.** Result 2 is the paper's most quotable and its
most fragile. Over the full population the structure–churn correlation is
indistinguishable from zero, but outliers and the single-file subset show the
relationship is weak, not absent. We report the pooled value, the subset, and the
outliers rather than only the flattering number.

**Reproduction cost.** The resource and every result build and analyse on a CPU
without any model run — deliberately, since the resource is for people whose
agents and budgets are small. The pipeline itself demonstrates the competition's
premise: useful agent infrastructure can be built on consumer hardware.

**Responsible release.** Competition-provided tasks, graphs, and embeddings are
never redistributed; we release only task identifiers and metrics derived from
them, plus scripts that rebuild those metrics for anyone with competition access.
Our mined tasks, graphs, and tooling are released openly with provenance to each
upstream pull request, preserving attribution to the original maintainers.

---

## 6. Conclusion

We introduced SWE-Pocket, a size-stratified evaluation resource for
consumer-hardware coding agents. It contributes (1) 153 Python tasks across two
strata — 129 provided large-library tasks and 24 mined compact-library tasks —
under one schema and one pipeline; (2) the finding that repository size is three
axes (breadth, coupling, depth) that node count alone misranks, and that those
axes are largely independent of the fix a task requires; and (3) a GPU-free
pipeline that generalises from the provided repositories to ones we mined. We
release everything needed to report the size axis in future benchmarks and to
study it in future agents.

**Code and data:** https://github.com/divinenwobodo19-creator/swe-pocket (code Apache-2.0, data CC-BY-4.0).
**Public notebook:** https://www.kaggle.com/code/divinenwobodo19/swe-pocket-reproduction

---

## References

[1] C. E. Jimenez et al. SWE-bench: Can Language Models Resolve Real-World GitHub Issues? ICLR 2024. arXiv:2310.06770.
[2] OpenAI. Introducing SWE-bench Verified. 2024.
[3] J. Yang et al. SWE-bench Multimodal: Do AI Systems Generalize to Visual Software Domains? 2024. arXiv:2410.03859.
[4] L. Zhang et al. SWE-bench Goes Live! 2025. arXiv:2505.23419.
[5] C. S. Xia et al. Agentless: Demystifying LLM-based Software Engineering Agents. 2024. arXiv:2407.01489.
[6] Y. Zhang et al. AutoCodeRover: Autonomous Program Improvement. ISSTA 2024. arXiv:2404.05427.
[7] J. Yang et al. SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering. NeurIPS 2024. arXiv:2405.15793.
[8] X. Wang et al. OpenHands: An Open Platform for AI Software Developers as Generalist Agents. 2024. arXiv:2407.16741.
[9] S. Ouyang et al. RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph. 2024. arXiv:2410.14684.
[10] Z. Chen et al. LocAgent: Graph-Guided LLM Agents for Code Localization. 2025. arXiv:2503.09089.
[11] D. Edge et al. From Local to Global: A Graph RAG Approach to Query-Focused Summarization. 2024. arXiv:2404.16130.
[12] R. Aleithan et al. SWE-Bench+: Enhanced Coding Benchmark for LLMs. 2024. arXiv:2410.06992.
[13] Y. Wang et al. Are "Solved Issues" in SWE-bench Really Solved Correctly? An Empirical Study. 2025. arXiv:2503.15223.
[14] B. Hui et al. Qwen2.5-Coder Technical Report. 2024. arXiv:2409.12186.
[15] D. Guo et al. DeepSeek-Coder: When the Large Language Model Meets Programming. 2024. arXiv:2401.14196.
[16] A. Lozhkov et al. StarCoder 2 and The Stack v2: The Next Generation. 2024. arXiv:2402.19173.
[17] S. Liang et al. The SWE-Bench Illusion: When State-of-the-Art LLMs Remember Instead of Reason. 2025. arXiv:2506.12286.
