Use `variable_lookup` when the analyst asks what a variable means, wants the exact code definition, or needs a shortlist of variables by model/domain/table.

Guidance:
- Prefer exact lookup with `{"code": "<variable_code>"}` when the analyst already provides a variable code.
- Use `{"query": "<natural language>", "model": "...", "domain": "...", "table": "..."}` when the analyst describes a concept instead of a code.
- Use filters without `query` to list variables for a model/domain/table.
- Do not invent variable definitions; rely on the CSV-backed catalog only.
- If multiple results are returned, summarize the ambiguity and cite the candidate codes back to the analyst.
