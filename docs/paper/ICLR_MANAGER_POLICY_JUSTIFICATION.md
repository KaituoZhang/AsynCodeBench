# ICLR Draft: Read-Only Manager Policy

The BibTeX entries used below are in
[`iclr_manager_policy_references.bib`](iclr_manager_policy_references.bib).
The text deliberately distinguishes literature support for role-separated
orchestration from the stronger claim that every manager should be read-only.
The literature supports the former; the latter is our controlled benchmark
design and is evaluated through an ablation.

## Recommended related-work paragraph

```latex
Hierarchical multi-agent systems commonly separate orchestration from
specialized execution. MetaGPT encodes role-specific software-engineering
workflows as standardized operating procedures
\citep{hong2024metagpt}, while Magentic-One assigns planning, progress
tracking, and replanning to an orchestrator that directs specialized agents
with distinct action capabilities \citep{fourney2024magenticone}. This
orchestrator--worker pattern is also documented in deployed agent systems,
where a lead model decomposes a task and delegates focused work to parallel
subagents \citep{anthropic2024effectiveagents,
anthropic2025multiagentresearch}. However, multi-agent systems need not
outperform a single agent: failures frequently arise from system
specification, inter-agent misalignment, and verification or termination
errors \citep{cemri2025mast}. These findings motivate evaluating both the
benefits and the coordination costs introduced by explicit role separation.
```

## Recommended method paragraph

```latex
\paragraph{Read-only coordination plane.}
To isolate coordination from implementation, we instantiate CAID with a
read-only manager. The manager may inspect repository state, run diagnostic
evaluations, plan, delegate, provide feedback, reassign work, and integrate
accepted specialist artifacts, but it cannot author production-code changes.
This capability separation follows the orchestrator--worker pattern used in
prior multi-agent systems \citep{fourney2024magenticone,
anthropic2024effectiveagents} and the broader practice of assigning agents
role-specific tool permissions \citep{anthropic2026subagents}. A particularly
direct precedent appears in Anthropic's reported DeepSearchQA multi-agent
configuration, where the orchestrator has no direct tools and can act only by
delegating to subagents \citep{anthropic2026opus46systemcard}. Our restriction
is an experimental-control choice rather than a claim that read-only managers
are universally optimal: it prevents the manager from becoming an additional
full-context coding agent and makes production changes attributable to
scope-constrained specialists.
```

## Recommended ablation paragraph

```latex
\paragraph{Manager-write ablation.}
We separately consider \textsc{CAID+Repair}, in which the manager may directly
modify the integrated repository during final reconciliation. This ablation
tests whether manager-authored repair can recover failed handoffs or incomplete
integration, while explicitly accounting for the additional coding authority
and compute. We therefore report \textsc{CAID-RO} as the primary coordination
condition and \textsc{CAID+Repair} as a distinct capability ablation rather
than combining them under a single CAID label. This distinction is important
because coordination overhead can exceed its benefit on tightly coupled or
sequential tasks \citep{cemri2025mast,anthropic2026whenmultiagent}.
```

## Short version for a space-constrained methods section

```latex
Following role-separated orchestrator--worker architectures
\citep{hong2024metagpt,fourney2024magenticone}, CAID uses a read-only manager
that plans, delegates, diagnoses, reassigns, and integrates specialist
artifacts but cannot author production changes. Tool-less orchestrators that
operate only through delegation have also been used in reported multi-agent
evaluations \citep{anthropic2026opus46systemcard}. This restriction isolates
coordination from an additional full-context coding agent; manager-authored
repair is evaluated separately as \textsc{CAID+Repair}.
```

## Citation-to-claim map

| Claim | Best citation | Strength and limitation |
| --- | --- | --- |
| Orchestrators plan, delegate, monitor, and replan while specialists execute | `fourney2024magenticone` | Academic system paper; strongest architectural citation |
| Software-engineering agents can be assigned explicit specialized roles | `hong2024metagpt` | ICLR 2024 paper; supports role separation, not manager read-only access |
| Orchestrator--worker is an established engineering pattern | `anthropic2024effectiveagents`, `anthropic2025multiagentresearch` | Official engineering evidence; not a peer-reviewed theorem |
| An orchestrator can be denied direct tools and restricted to delegation | `anthropic2026opus46systemcard` | Direct implementation precedent, but from a research/search evaluation rather than software engineering |
| Agents may receive role-specific and restricted tool permissions | `anthropic2026subagents` | Direct community/product practice; use as supporting evidence |
| Multi-agent coordination can underperform because of handoffs and system design | `cemri2025mast` | Academic empirical evidence supporting the need for controlled protocols and diagnostics |
| Multi-agent overhead can exceed benefits on tightly coupled work | `anthropic2026whenmultiagent` | Engineering observation; pair with MAST rather than citing alone |

## Claims to avoid

Do not write:

```latex
Prior work proves that multi-agent managers must be read-only.
```

Use:

```latex
Prior systems motivate separating orchestration from specialized execution;
we operationalize this separation with a read-only manager to obtain a
controlled and attributable coordination condition.
```

Also avoid treating the Anthropic DeepSearchQA configuration as a
software-engineering result. It is a direct precedent for a tool-less
orchestrator action space, not evidence that the same restriction necessarily
improves repository-level coding performance.

## ICLR integration

With `natbib`, add the bibliography file to the paper without the `.bib`
suffix, for example:

```latex
\bibliography{iclr_manager_policy_references}
```

If the main project already has a bibliography database, copy the entries into
that database instead of declaring a second `\bibliography` command. The
standard ICLR template supports `\citet{...}` and `\citep{...}`.
