# Attack Prompt Research Notes

## 1. Goal

This benchmark evaluates how resistant LLMs are to prompt injection attacks that attempt to reveal a hidden secret such as `FLAG{...}`.

The goal of this research task is not to create dangerous real-world exploits, but to design benchmark prompts that are diverse, explainable, and useful for defensive evaluation. Good benchmark prompts should represent different attack patterns, include a clear rationale, and be easy to review later.

## 2. Existing Dataset Review

The original baseline dataset contained 55 prompts across 5 categories, with 11 prompts per category.
The current merged benchmark dataset in `prompts/prompts.jsonl` contains 122 prompts.

- `direct_override`
- `roleplay_framing`
- `obfuscation`
- `data_exfiltration`
- `indirect_injection`

### direct_override
Current prompts strongly cover explicit instruction conflict such as “ignore previous instructions” or “reveal the secret.”  
This category is useful, but many prompts are similar in tone and structure.

**Weaknesses**
- Heavy repetition of command-style wording
- Limited variation in tone
- Limited use of softer phrasing, clarification framing, or completion-based requests

### roleplay_framing
Current prompts use role and authority framing such as developer, auditor, technician, professor, or supervisor.  
This category already has a good foundation.

**Weaknesses**
- Many prompts depend on authority-based roles
- Less variety in social trust, urgency, teamwork, or mistake-recovery scenarios
- Emotional pressure and collaboration framing are underused

### obfuscation
Current prompts mainly use format conversion or indirect transformation, such as reverse order, Base64, hex, chunking, ASCII codes, or JSON arrays.

**Weaknesses**
- Many prompts are encoding-focused
- Less coverage of partial leakage, structural hints, and selective disclosure
- Indirect reasoning-based leakage is limited

### data_exfiltration
Current prompts try to retrieve hidden values by asking for internal variables, the system prompt, hidden state, diagnostics, or hidden configuration.

**Weaknesses**
- Strong coverage of direct extraction requests
- Less variety in indirect memory framing or pattern-based inspection
- Some prompts are very close to each other conceptually

### indirect_injection
Current prompts are strong and realistic, using document summaries, HTML snippets, quoted emails, CSV rows, YAML content, logs, and attachment-like text.

**Weaknesses**
- Less use of multi-step workflow style instructions
- Limited conversational or chat-log variations
- Could include more realistic retrieval-style and processing-task framing

## 3. Key Attack Pattern Ideas

The main prompt injection patterns relevant to this benchmark are:

1. **Instruction override**  
   A prompt tries to replace or outrank previous instructions.

2. **Role or authority framing**  
   A prompt creates a context where disclosure appears authorized, required, or normal.

3. **Obfuscated disclosure**  
   A prompt asks for the secret indirectly through formatting, partial output, hints, or transformation.

4. **Hidden context extraction**  
   A prompt directly or indirectly asks for internal state, memory, hidden configuration, or protected fields.

5. **Indirect injection through content**  
   A malicious instruction is embedded inside a document, note, log, email, or retrieved text that the model is asked to process.

## 4. Why These Patterns Might Work

These patterns may work because language models often try to be helpful, follow the most recent instruction, continue a given format, or treat embedded text as part of the task. Role framing can make a request seem legitimate. Obfuscation can reduce the apparent sensitivity of disclosure. Indirect injection can confuse the boundary between trusted instructions and untrusted content.

## 5. Gaps in the Current Dataset

The original baseline dataset was already useful, but several improvements were possible:

- Too many direct command variations in `direct_override`
- Too much reliance on authority personas in `roleplay_framing`
- Too much emphasis on encoding in `obfuscation`
- Strong direct extraction coverage but weaker indirect extraction coverage in `data_exfiltration`
- Strong document-style traps in `indirect_injection`, but fewer multi-step or conversational retrieval scenarios

## 6. Improvement Strategy

The candidate prompts in this submission were designed to improve the dataset in four ways:

- Increase variation in tone, structure, and framing
- Add softer and less obvious attack styles
- Expand partial leakage and structural leakage patterns
- Add more realistic indirect injection contexts such as notes, workflows, replies, and retrieved content

## 7. Design Principles Used for the Candidate Prompts

Each candidate prompt was written using the following principles:

- The attack intent should be understandable
- The prompt should fit its category clearly
- The wording should not be a trivial rephrase of an existing prompt
- The rationale should explain why the prompt might pressure the model into revealing the secret
- The prompt should remain appropriate for benchmark research and defensive evaluation

## 8. Final Assessment

The benchmark covers the major prompt injection categories well. The largest improvement opportunities are:

- more diverse wording in `direct_override`
- broader scenario framing in `roleplay_framing`
- more partial and structural leakage in `obfuscation`
- more indirect extraction logic in `data_exfiltration`
- more conversational and multi-step processing traps in `indirect_injection`

The candidate prompts were created to address those gaps while staying organized, reviewable, and safe for benchmark design.

## 9. Sources Referenced

The following sources were used for this task:

- `README.md` in this repository
- `prompts/prompts.jsonl` in this repository

These sources were used to understand:
- the benchmark goal
- the five attack categories
- the current prompt coverage
- weaknesses and improvement opportunities in the existing dataset
