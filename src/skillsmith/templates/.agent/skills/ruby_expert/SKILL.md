---
name: ruby_expert
description: Ruby and Rails specialist. Productive, idiomatic web development with a focus on developer happiness.
version: 1.0.0
tags:
  - ruby
  - rails
  - backend
  - web
  - language
---

# Ruby Expert

Professional guidelines for Ruby and Ruby on Rails development.

## Philosophy

- **Developer Happiness**: Write code that is beautiful, readable, and fun to work with.
- **Convention over Configuration**: Follow established patterns to reduce decision fatigue.
- **DRY (Don't Repeat Yourself)**: Eliminate redundancy through modularity and metaprogramming.

## Patterns

- **ActiveRecord**: Use the ORM effectively, avoiding N+1 queries with `includes`.
- **Service Objects**: Move complex business logic out of models and controllers.
- **Concerns**: Extract shared logic into reusable modules.
- **TDD/BDD**: Use RSpec for descriptive, behavior-driven testing.

## Best Practices

- **Style Guide**: Follow the community Ruby Style Guide (RuboCop).
- **Gem Management**: Use Bundler for dependency management.
- **Security**: Be vigilant about SQL injection, XSS, and mass assignment in Rails.
- **Metaprogramming**: Use sparingly; prioritize clarity over "clever" code.
