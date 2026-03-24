---
version: 0.1.0
name: agno-ai-best-practices
description: Use this skill when building AI agents with frameworks like Agno, LangChain, or similar. It defines agent architecture, tool design, and reliability standards.
tags: [agents, ai, framework, langchain, agno]
---

# 🧠 AI Agent Best Practices

> **Philosophy:** Agents are powerful but unpredictable. Build with guardrails.

## 1. Core Architecture
| Pattern | Good | Bad |
|---|---|---|
| Agent Scope | `ClassifierAgent`, `SummarizerAgent` | `GodAgentThatDoesEverything` |
| Tool Design | Typed args, descriptive docstrings | Magic strings, no types |

*   **One Agent = One Responsibility.** Single-purpose agents are more reliable.
*   **Tools as First-Class Citizens:**
    *   Tools should be well-typed Python/TS functions.
    *   LLMs read type hints and docstrings to understand how to use tools!

## 2. Agent Design
*   **System Prompts:**
    *   **Role:** "You are a customer service assistant."
    *   **Output Format:** "Return JSON only. Schema: `{...}`"
    *   **Constraints:** "Never make up information. Say 'I don't know' if unsure."
*   **Memory:**
    *   Short-term: Conversation history within a session.
    *   Long-term: Vector DB for RAG tasks (when needed).

## 3. Performance & Reliability
| Model Type | Use Case |
|---|---|
| Fast/Small (GPT-3.5, Gemma) | Classification, extraction, simple tasks. |
| Powerful (GPT-4, Claude) | Complex reasoning, coding, multi-step tasks. |

*   **Observability:** Log all inputs, outputs, and tool calls.
*   **Error Handling:** Agents should gracefully handle tool failures, not crash.
*   **Retries:** Implement retry logic for transient API failures.

## 4. Deployment
*   **Statelessness:** Agents fetch state, act, then save. No in-memory state.
*   **Async:** Use async/await to prevent blocking during API calls.
*   **Cost Awareness:** Log token usage. Optimize prompts to reduce costs.

## Examples
*   **New agent:** Define system prompt -> Create tools -> Wire to API -> Write tests with mocked responses.

## Guidelines
*   Mock LLM responses in tests to avoid costs and flakiness.
*   Use `temperature=0` in tests for deterministic outputs.
*   Always have a human-in-the-loop for high-stakes actions.
