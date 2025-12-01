# Problem

## Overview

A framework is needed for experimenting with automated code transformation pipelines against pseudo codebases using highly granular transformation steps.

The system should support repeatedly applying small isolated transformations to codebases while avoiding unnecessary recomputation through dependency-aware caching and state tracking.

The effort focuses on exploring transformation orchestration, state attestation, dependency scoping, and incremental execution models rather than building monolithic code migration systems.

---

# Core Problem Areas

## Pseudo Codebase Environment

The system operates on pseudo repositories rather than actual Git repositories.

The workflow involves:

- Maintaining a stable source directory structure representing various codebases and scenarios
- Copying those codebases into temporary git-ignored working directories
- Performing transformations against temporary working copies
- Preserving the original source examples separately from transformed outputs

The environment must simulate repository evolution without relying on actual Git repository mechanics.

---

# Incremental Code Transformation

The system needs to support automated code transformations that evolve a codebase over time through many small isolated operations.

Examples include:

- Creating missing generated files
- Updating generated artifacts
- Adding Makefiles
- Adding Makefile targets
- Running formatters
- Running analyzers
- Performing small automated code edits
- Applying language-native transformations

The emphasis is on microscopic transformations rather than large sweeping migrations.

---

# Generated File Management

Certain files should be treated as generated artifacts rather than manually maintained content.

For example:

- A code map file may be automatically generated
- The generator should create the file if missing
- Subsequent transformations should populate or update it automatically
- Manual editing should be discouraged or disallowed

The system must distinguish between generated state and manually maintained state.

---

# Transformation Dependency Tracking

Each transformation only depends on a subset of the overall codebase state.

For example:

- A code map transformer only cares about:
  - Relevant directories
  - The generated code map file
  - Specific structural inputs

Other unrelated changes should not force the transformer to rerun.

The framework must support fine-grained dependency boundaries for individual transformations.

---

# Transformation Attestation

The system requires a way to determine whether a transformation has already successfully executed against a given codebase state.

Each transformation should be able to produce some form of attestation indicating:

- The transformation completed successfully
- The transformation applied to a specific codebase state
- The current state remains valid for that transformation

The framework needs a reliable mechanism for expressing transformation completion and validity.

---

# Incremental Execution and Caching

A major problem area is avoiding unnecessary recomputation.

The system cannot rerun every transformation every time because:

- Transformation counts may become very large
- Repeated execution would become computationally expensive
- Many transformations may already be satisfied

The framework must support incremental execution and dependency-aware caching.

---

# Simulated Repository State

Because the codebases are not actual Git repositories, the system must simulate repository state progression.

The framework requires:

- Synthetic commit identifiers
- Generated UUIDs or pseudo SHAs
- State tracking mechanisms representing transformed repository states

Every transformation that changes the codebase may generate a new synthetic state identifier.

---

# Selective Transformation Re-Execution

Transformers should only rerun when their relevant dependency boundaries change.

The framework must support:

- Per-transform dependency definitions
- State comparison
- Input boundary tracking
- Incremental invalidation

The objective is to avoid rerunning transformations when their relevant inputs remain unchanged.

---

# Constraints

## Architectural Constraints

- Codebases are pseudo repositories rather than real Git repositories
- Transformations occur inside temporary working copies
- Original source examples remain unchanged

## Performance Constraints

- Large numbers of micro-transformations must remain computationally feasible
- Full recomputation is unacceptable at scale
- Transformation execution must become incremental

## Maintainability Constraints

- Transformations should remain small and isolated
- Generated artifacts should remain machine-managed
- Dependency scopes should remain explicit and minimal