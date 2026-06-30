# Qualification Protocol v0.2

Status: frozen for pilot annotation  
Specification: `SPECIFICATION_v0.2.md`  
Freeze date: 2026-06-22

## Primary evidence

Primary task qualification uses only preregistered, agent-independent public
evidence:

- public issue or task specification;
- publicly implicated source modules;
- public module count;
- static dependency edges among implicated modules;
- executable test targets and their independence;
- measured test/build duration, command, return code, timeout status, and
  environment;
- candidate parallel subproblems;
- public cross-module constraints;
- expected implementation, testing, review, and integration overlap;
- expected shared-resource contention;
- explicit evidence-source records.

Gold patches, solution refs, and reference diffs are prohibited as primary
evidence. If later used for secondary analysis, they must be disclosed only in
`gold_informed_secondary_label`.

Code suggestions already contained in an official public issue remain part of
the public problem statement. They must not be conflated with hidden dataset
solution fields.

## Annotation

- Every finalized task requires exactly two independent annotators.
- Annotators must not see each other's decision before submission.
- Label, inclusion, and exclusion-reason disagreements require an independent
  adjudicator.
- All candidate and excluded records remain in the manifest.
- Agreement is reported before adjudication using raw rates and Cohen's kappa.

## Frozen machine-readable assets

At freeze time:

```text
qualification schema SHA-256:
a3f4c576b38752cdfdaaed1e64903e5dd2ffcef64bde404dfe910e7b4fb556bf

protocol configuration SHA-256:
042df78d68e3ff1b7e07bed577bba4053e98070d85733f6784fe1de866379ece
```

Files:

- `schemas/v0.2/qualification_card.schema.json`
- `configs/tasks/qualification_protocol_v0.2.json`
- `manifests/candidates/qualification_batch.template.json`

Changing required primary evidence, annotation semantics, task classes, or
gold-information policy requires specification review. Mechanical bug fixes
that preserve these semantics require regenerated hashes and a documented
protocol revision.

## Commit0 candidate generation

The initial Commit0 inventory is generated exclusively from the `commit0` ref:

- `git ls-tree commit0`;
- `git show commit0:<path>`;
- `git archive commit0`;
- `spec.pdf.bz2` or README material present at `commit0`;
- Python source incomplete markers;
- static imports;
- test files;
- baseline pytest execution on the exported `commit0` tree.

The extractor must not inspect `master`, `develop`, reference refs, or
`commit0..reference` diffs. Repository symlinks and hardlinks are not followed
during materialization.

The generated inventory is unlabelled. Automated module and dependency
evidence assists annotators but does not determine the final
parallelizability label.
