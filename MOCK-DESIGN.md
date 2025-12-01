# Mock Design

## Purpose

This document is a high-level mock design for the system described in `PROBLEM.md`, `TECHNICAL.md`, and `VISION.md`.

Its job is to answer a narrow but important question:

Can the proposed transformation framework realistically work as a coherent system?

This is intentionally not a detailed implementation spec. It avoids locking the project into specific schemas, storage formats, APIs, or low-level execution details unless those details are necessary to judge feasibility.

## Source Interpretation

The three source documents are strongly aligned. They describe a system that should be understood as:

- an incremental transformation engine
- operating over pseudo codebases rather than live Git repositories
- built from many tiny deterministic or mostly deterministic transformations
- optimized around scoped invalidation, attestation, and cache reuse
- closer in spirit to an incremental compiler or build graph than a migration runner

That framing matters. If this is treated like a traditional script pipeline, the design will likely collapse under recomputation, ambiguity, and poor invalidation behavior. If it is treated like a small incremental state engine, the proposed pieces fit together much more naturally.

## Goals, Constraints, Assumptions

### Primary Goals

- Repeatedly evolve pseudo codebases through microscopic automated transformations.
- Avoid unnecessary reruns through dependency-aware skipping and reuse.
- Treat generated artifacts as machine-owned outputs.
- Simulate codebase state progression without requiring real Git repository mechanics.
- Support future growth toward large numbers of transformations.

### Explicit Constraints

- Canonical example codebases remain stable and should not be mutated in place.
- Transformations run in temporary or derived working copies.
- Full recomputation is unacceptable once transformation counts become large.
- Transformations should stay small, isolated, and conceptually simple.
- Dependency scopes should be explicit and minimal.

### Implied Assumptions

- Most useful transformations can declare a meaningful read boundary and write boundary.
- At least an early subset of transformations can behave deterministically enough for caching to be trustworthy.
- A synthetic notion of state can be good enough for reuse decisions without fully emulating Git.
- Incremental invalidation can be made cheaper than rerunning everything.

### Likely Non-Goals

The source documents do not point toward:

- replacing Git or reproducing its full object model
- building a general-purpose workflow orchestrator
- supporting highly interactive manual editing inside the transformation loop
- starting with deep semantic dependency tracking across all languages

Those may become adjacent concerns later, but they should not shape the first architecture.

## Viability Verdict

The system is conceptually viable.

The idea is strongest when framed as an incremental derivation engine with these properties:

- immutable canonical inputs
- disposable or rematerializable workspaces
- explicit transformation contracts
- scoped observations of relevant state
- attestations that act as reuse claims
- a scheduler that reruns only what became invalid

The hard part is not "can small transformations edit files?" That part is straightforward.

The hard part is whether the engine can make correct and cheap decisions about:

- what changed
- which transformations care
- whether a previous success is still valid
- how far invalidation should propagate

If those questions are answered cleanly, the overall architecture is implementable. If they are not, the system will either rerun too much and become expensive, or rerun too little and become incorrect.

## Recommended System Shape

The most coherent design is a layered system with very clear boundaries.

### 1. Canonical Example Layer

This layer stores the stable pseudo codebases used as experimental inputs.

Responsibilities:

- hold named baseline scenarios
- remain immutable during runs
- provide repeatable starting points

This should behave like fixture data, not a live workspace.

### 2. Workspace Materialization Layer

This layer creates disposable or derived workspaces from canonical examples or previously known synthetic states.

Responsibilities:

- copy or materialize a workspace for execution
- isolate mutable execution from canonical inputs
- support repeatable initialization
- optionally support rematerialization of known derived states

This is the execution sandbox of the system.

### 3. Observation and Fingerprinting Layer

This layer answers the most important operational question:

What part of the workspace does a transformation actually depend on?

Responsibilities:

- observe relevant files, directories, or other supported state slices
- compute stable fingerprints for those slices
- provide shared change knowledge to the scheduler
- avoid requiring each transformation to rediscover the world independently

This layer is central to both correctness and scalability.

### 4. Transformation Layer

This layer defines the micro-transformations themselves.

Each transformation should conceptually declare:

- what it reads
- what it may write or own
- whether it mutates state or only validates it
- what environmental/tooling assumptions it depends on
- what attestation it can emit after successful execution

The framework should strongly prefer transformations that are:

- small
- explicit
- idempotent or convergent
- deterministic where possible
- narrow in write scope

### 5. Scheduling and Invalidation Layer

This layer decides what needs to run, when it should run, and why.

Responsibilities:

- identify candidate transformations
- skip transformations with still-valid attestations
- rerun transformations whose relevant inputs changed
- propagate invalidation to downstream dependents
- continue until the workspace reaches a stable result

This should behave like an incremental graph engine, not a dumb linear script runner.

### 6. Attestation and Cache Layer

This layer stores reusable execution knowledge.

Responsibilities:

- record that a transformation validated or changed a particular relevant state
- link that result to a synthetic repository state
- support reuse, skipping, and explanation
- preserve enough lineage to debug scheduler behavior

This is the memory of the framework.

## Core Conceptual Workflow

The most natural high-level flow looks like this:

1. Select a canonical pseudo codebase.
2. Materialize a disposable workspace.
3. Collect or refresh observations for the relevant workspace slices.
4. Ask the scheduler which transformations are unknown, invalid, newly applicable, or blocked.
5. Run only the eligible transformations that need work.
6. If a transformation changes the workspace, update the affected observations and advance synthetic state.
7. Re-evaluate only the transformations whose dependency slices may now be stale.
8. Continue until the system reaches a fixed point or a defined stopping rule.
9. Persist attestations, lineage, and optionally reusable derived state.

This flow fits the generated artifact use case especially well. It also matches the stated desire to support many tiny, composable, continuously reusable steps.

## Key Design Boundaries

Several boundaries should be made explicit early because they shape the entire system.

### Immutable Inputs vs Mutable Execution

Canonical examples should never be mutated in place. All writes happen in workspaces or derived states.

### Human-Owned Files vs Machine-Owned Files

Generated artifacts need an ownership model. Without it, the system cannot reliably distinguish:

- intended user edits
- stale generated content
- invalid manual intervention

### Read Boundaries vs Write Boundaries

Declaring writes alone is not enough. Incremental reuse depends on declared reads and dependency slices.

### Validation vs Mutation

Some transformations will observe and attest without modifying files. Others will mutate state. The framework should support both concepts separately even if they share execution machinery.

### State Identity vs Event History

Synthetic state should represent a meaningful derived workspace state, not a full fake Git history. The system needs enough lineage for reuse and debugging, not full repository semantics.

## Synthetic State Model

The synthetic state idea is workable, but only if its meaning stays narrow.

The synthetic identifier should answer:

- what derived state the framework believes the workspace is in
- what meaningful mutations led there
- what attestations are valid for that state

It does not need to answer:

- branch semantics
- merge semantics
- remote synchronization
- the full Git object model

A useful mental model is "state identity for an incremental engine," not "Git clone in miniature."

## Generated Artifact Model

The generated artifact vision is realistic and likely a strong early proving ground.

Conceptually, the framework needs a way to say:

- this output is machine-owned
- this transformation is responsible for establishing or refreshing it
- this output should be regenerated from source state rather than manually maintained

This is less about file generation itself and more about policy. The system becomes much easier to reason about once ownership is explicit.

## Why This Can Work

The proposed pieces fit together coherently if the project stays disciplined about early scope.

This design is especially plausible because:

- the source documents consistently describe one architectural direction
- pseudo repositories simplify the environment instead of complicating it
- generated artifacts are a natural fit for deterministic micro-transformations
- scoped invalidation is a known class of problem with strong analogies in build systems and compilers
- the system does not need to solve every advanced case on day one to be valuable

An early implementation can be credible without being universal.

## Major Risks and Ambiguities

### 1. Dependency Scope Is Still Too Abstract

The documents are correct to emphasize dependency boundaries, but they do not yet say what those boundaries are made of.

Open possibilities include:

- files
- directories
- path sets
- generated metadata
- semantic facts

This is the single most important unresolved design area because it directly affects correctness, performance, and authoring complexity.

### 2. Ordering and Convergence Are Underspecified

Microscopic transformations are a strength, but they create interaction risks.

Examples:

- one transformation creates a file that another reformats
- an analyzer generates information that unlocks a later change
- two transformations repeatedly rewrite the same file in slightly different ways

The framework needs a clear position on:

- ordering
- fixed-point behavior
- oscillation prevention
- bounded rerun semantics

### 3. Synthetic State Needs a Crisp Meaning

The sources mention UUIDs, pseudo SHAs, and synthetic commits, but the design intent is still too loose.

Open questions include:

- whether identity is content-derived, event-derived, or hybrid
- whether equivalent content on different machines should compare equal
- whether identity exists per whole workspace, per slice, or per transformation result

These choices affect attestation validity and cache reuse.

### 4. External Tool Determinism Is a Real Risk

Formatters, analyzers, and language-native tools may depend on:

- tool version
- runtime environment
- config files
- filesystem ordering
- hidden external state

If those influences are not captured conceptually, the engine may reuse stale results incorrectly.

### 5. Observation Cost Could Dominate

A system with thousands of tiny transformations only scales if change detection is shared and cheap.

If every transformation independently scans the tree to decide whether it should run, the framework will degrade quickly. That suggests a central observation strategy is likely necessary.

### 6. Overlapping Write Responsibility Could Destabilize the Model

Small transformations are not automatically isolated. If multiple transformations can rewrite the same path or region, the system needs a policy for:

- ownership
- precedence
- conflict detection
- composition expectations

Without that, "micro" can still become "fragile."

### 7. Failure Semantics Are Not Yet Defined

A transformation can partially mutate a workspace and then fail.

The design needs a high-level answer for:

- when synthetic state advances
- whether failed runs can leave reusable observations behind
- whether workspaces are repaired, rolled forward, or discarded
- how trust in attestations is preserved after failure

### 8. Debuggability Will Matter Early

An incremental engine is only usable if people can understand its decisions.

Users will need to answer:

- why did this run?
- why was this skipped?
- what changed?
- which attestation became invalid?
- which transformation last touched this generated output?

This may not require a polished UI early, but it does require a deliberate design for explainability.

## Unresolved Decisions That Block Confident Design

The following decisions do not need full implementation detail yet, but they do need directional answers before the architecture hardens.

### Transformation Model

- Are transformations arbitrary command runners, or structured adapters with declared behavior?
- Are validation-only transformations a first-class concept?
- Can transformations directly depend on other transformations, or only on observed state and explicit prerequisites?

### Dependency Model

- Is phase one limited to filesystem-level dependencies?
- Are semantic dependencies intentionally deferred?
- How are dependency declarations authored and validated?

### State Model

- Is synthetic state content-addressed, event-addressed, or hybrid?
- Must the system preserve all intermediate states, or only reusable milestones?
- Can derived states be rematerialized directly, or does every run always begin from canonical inputs?

### Execution Model

- Is fixed-point convergence required in phase one?
- Should phase one be deterministic-first and serial?
- How are cycles, conflicts, and oscillations prevented?

### Ownership Model

- How are machine-owned outputs designated?
- What happens if a human edits one?
- Are there reserved paths or only reserved files?

## Clarifying Questions

These are the highest-value questions surfaced by the source documents.

1. Is the first target primarily a research harness for experimenting with orchestration strategies, or a framework expected to become stable operational tooling?
2. Can the early system limit itself to deterministic or tightly controlled transformations, or must it support arbitrary external tools immediately?
3. Is automatic fixed-point convergence a hard requirement for the first meaningful version, or is an explicitly ordered iterative pipeline acceptable initially?
4. Should synthetic state identifiers compare equal across machines when content and tool context are equivalent, or only be unique within one environment?
5. Is the initial dependency model expected to reason only about files and directories, or also about semantic facts such as symbols, imports, or generated code maps?
6. Are generated artifacts expected to live inside the pseudo codebase tree, outside it, or both?
7. Is preserving complete intermediate lineage important, or is the main objective simply to reuse work and reach the latest valid state efficiently?

## Recommended Initial Direction

The project appears most likely to succeed if the first implementation stays intentionally narrow.

Recommended early direction:

- deterministic-first transformations
- filesystem-level dependency slices before semantic dependency slices
- serial scheduling before parallel scheduling
- explicit machine-owned artifact policy
- bounded fixed-point or staged convergence instead of unlimited rerun loops
- shared observation/fingerprinting rather than per-transform tree scanning

This is enough to validate the architecture without prematurely taking on the hardest possible cases.

## Suggested Repository Shape

One possible high-level repository organization:

- `examples/` for canonical pseudo codebases and scenarios
- `workspaces/` for disposable materialized runs
- `cache/` for attestations, fingerprints, and optionally reusable derived states
- `engine/` for scheduling, invalidation, and synthetic state progression
- `transformers/` for micro-transform definitions
- `adapters/` for tool-specific integrations such as formatters and analyzers
- `docs/` for decisions, experiments, and design notes

This is only a conceptual organizational suggestion. The important separation is between immutable inputs, mutable execution space, reusable knowledge, and transformation logic.

## Recommended Validation Plan

The next step should be a focused set of architectural experiments, not a broad implementation push.

### Experiment 1: Minimal Incremental Loop

Prove that the system can:

- materialize a workspace
- run one deterministic transformation
- emit an attestation
- skip rerun when the relevant input slice is unchanged

### Experiment 2: Generated Artifact Ownership

Prove that the system can:

- create a missing generated file
- regenerate it deterministically
- detect or reject out-of-band manual edits

### Experiment 3: Scoped Invalidation

Prove that an unrelated workspace change does not trigger reruns for a transformation whose declared inputs did not change.

### Experiment 4: Multi-Step Convergence

Prove that several small transformations can reach a stable final state without oscillation.

### Experiment 5: Observation Cost

Measure whether the cost of deciding what changed remains acceptable as the number of transformations grows.

These experiments validate the central claims of the architecture much better than an early full implementation would.

## Final Assessment

The proposed system is fundamentally implementable.

Its strongest interpretation is a deterministic-first incremental transformation framework that:

- starts from immutable pseudo codebases
- materializes disposable workspaces
- applies tiny explicit transformations
- tracks scoped dependencies and synthetic state
- emits attestations that justify reuse
- converges toward a valid transformed state with minimal recomputation

The largest design pressures are not signs that the vision is broken. They are the places where the vision needs sharper decisions:

- dependency representation
- state identity semantics
- convergence and scheduling behavior
- generated artifact ownership
- scalability of observation and invalidation

If those fronts are handled deliberately, the proposed components fit together coherently and the project has a strong conceptual foundation.
