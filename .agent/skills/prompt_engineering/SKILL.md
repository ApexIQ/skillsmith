---
version: 1.0.0
name: prompt_engineering
description: Expert guide on prompt engineering for 2024-2025 models (GPT-4o, Claude 3.5, o1, o3, Gemini 2.0). Covers reasoning models, delimiters, structured output, and context engineering.
tags: [prompting, reasoning, llm, optimization, structured-output]
---

# ✍️ Prompt Engineering (2025 Edition)

> **Philosophy:** Direct models through clear constraints and structural cues. Modern LLMs prioritize well-formatted, context-rich instructions over simple keywords.

## 🧠 Reasoning Model Strategy (o1, o3, DeepSeek-R1)
For models with internal "Think" cycles:
- **Quiet Mode:** Do NOT ask for "chain of thought" or "step by step" logic. These models do it internally and redundant prompting can degrade latency or follow-through.
- **Focus:** Define the **Input**, **Constraints**, and **Expected Output Schema** with extreme precision.
- **Evaluation:** Provide rubrics for how the model should verify its own work.

## 1. Delimiters and XML Tagging
Use standard delimiters (XML tags, backticks, or separators) to clearly distinguish instructions from data.
- **Example:**
  ```markdown
  <instruction>Extract entities from the text below.</instruction>
  <text>John Doe moved to Berlin in 2024.</text>
  ```
- **Benefit:** Prevents "prompt injection" where the data content overwrites the instructions.

## 2. Few-Shot Structural Prompting
Show example "Thought -> Action" sequences to steer complex agent behavior.
- Use 2-3 high-quality examples of the *full reasoning process*.

## 3. Negative Constraints (Avoidance)
Be explicit about what NOT to do.
- **Bad:** "Don't use Python 2."
- **Good:** "Use Python 3.12+ features. Avoid any legacy constructs from Python 2.x."

## 4. Output Formatting (JSON/Markdown)
Force specific formats for programmatic use.
- Use **JSON Schema** in the prompt to ensure the keys and types are strictly followed.

## Advanced Patterns
- **Meta-Prompting:** Use the model to help you refine your own prompt.
- **Context Injection:** See `agentic_context_engineering` for managing long-term memory.
- **Workflow Patterns:** See `anthropic_workflow_patterns` for orchestration logic.

## Anti-Patterns (2025 Update)
- **Prompt Dumping:** Adding irrelevant code snippets (use `skillsmith budget` to check token usage).
- **Keyword Soup:** Relying on magic words like "Expert" (effective prompts now rely on specific instructions and role-play).
- **Ignoring Failures:** Not providing instructions on what the model should do when it *cannot* complete the task.

## Guidelines
*   **Be Atomic:** One prompt per specific sub-task.
*   **Verify Schema:** Always validate JSON outputs before final processing.
*   **Iterate with Evaluation:** Use `Evaluator-Optimizer` patterns for production-grade output.
