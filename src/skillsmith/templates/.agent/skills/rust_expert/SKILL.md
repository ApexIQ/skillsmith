---
name: rust_expert
description: Systems programming with Rust. Ownership, borrowing, lifetimes, and safety patterns.
version: 1.0.0
tags:
  - rust
  - backend
  - systems
  - language
---

# Rust Expert

Professional guidelines for systems programming in Rust.

## Philosophy

- **Safety First**: Leverage the borrow checker to eliminate data races and memory errors.
- **Zero-Cost Abstractions**: Use high-level constructs that compile down to efficient machine code.
- **Fearless Concurrency**: Use Rust's type system to ensure thread safety.

## Patterns

- **RAII**: Resource Acquisition Is Initialization for memory and resource management.
- **Error Handling**: Use `Result` and `Option` instead of exceptions. Use `anyhow` for apps and `thiserror` for libraries.
- **Traits**: Define shared behavior through traits. Prefer composition over inheritance.
- **Async**: Use `tokio` for high-performance asynchronous I/O.

## Best Practices

- **Cargo**: Use `cargo fmt` and `cargo clippy` religiously.
- **Testing**: Write unit tests in the same file and integration tests in `tests/`.
- **Documentation**: Use `///` for doc comments and `cargo doc` to generate documentation.
- **Unsafe**: Minimize and audit all `unsafe` blocks. Document why they are necessary.
