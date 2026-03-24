---
name: cpp_expert
description: Modern C++ specialist (C++17/20/23). Smart pointers, move semantics, and generic programming.
version: 1.0.0
tags:
  - cpp
  - c++
  - systems
  - performance
  - language
---

# C++ Expert

Professional guidelines for modern C++ development.

## Philosophy

- **Modern C++**: Use C++11/14/17/20/23 features to write safer and more expressive code.
- **Performance**: High-performance systems with fine-grained control over hardware.
- **Resource Management**: Strict adherence to RAII and smart pointers.

## Patterns

- **RAII**: Always manage resources (memory, file handles, locks) through object lifetimes.
- **Move Semantics**: Use `std::move` and move constructors to avoid expensive copies.
- **Templates**: Generic programming and metaprogramming for type-safe, reusable code.
- **STL**: Maximize usage of the Standard Template Library (containers, algorithms).

## Best Practices

- **Smart Pointers**: Prefer `std::unique_ptr` by default, `std::shared_ptr` only when ownership is shared.
- **Const Correctness**: Use `const` everywhere possible to prevent unintended mutations.
- **No Raw New/Delete**: Use `std::make_unique` and `std::make_shared` instead of raw `new`.
- **Auto**: Use `auto` for complex iterator types but prefer explicit types for clarity in business logic.
