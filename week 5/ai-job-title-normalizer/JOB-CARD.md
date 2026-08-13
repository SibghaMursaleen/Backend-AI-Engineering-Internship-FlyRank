# JOB CARD: AI Job Title Normalizer

## Purpose
Normalizes a messy, abbreviated, or unstructured job title into a canonical software engineering title and seniority level using a structured AI workflow.

## Contract Schema

### Input Schema
```json
{
  "text": "string (1-200 characters)"
}
```

### Output Schema
```json
{
  "canonical_title": "Software Engineer" | "Backend Engineer" | "Frontend Engineer" | "Full Stack Engineer" | "Data Engineer" | "ML Engineer" | "DevOps Engineer" | "Other",
  "level": "intern" | "junior" | "mid" | "senior" | "lead" | "unknown",
  "confidence": 0.0 - 1.0,
  "reason": "string"
}
```

### Allowed Values

#### Canonical Titles:
- `Software Engineer`
- `Backend Engineer`
- `Frontend Engineer`
- `Full Stack Engineer`
- `Data Engineer`
- `ML Engineer`
- `DevOps Engineer`
- `Other`

#### Seniority Levels:
- `intern`
- `junior`
- `mid`
- `senior`
- `lead`
- `unknown`

## Critical Constraints & Validation Rules
1. **No External Values**: The output must only use the allowed canonical titles and seniority levels listed above. No other values are permitted.
2. **No Arbitrary Fields**: The output must contain only the four specified fields: `canonical_title`, `level`, `confidence`, and `reason`.
3. **Robust Confidence Scores**: High confidence (e.g. `> 0.85`) should be reserved for clear matches. Indicated abbreviations (like "Sr. SWE II") can map to high confidence, while highly ambiguous inputs (like "Ninja Guru") should map to low confidence, "Other", and "unknown".
4. **Fallback Strategy**: If the model is uncertain, it should fall back to `Other` and/or `unknown` rather than guessing with high confidence.
5. **No Raw Model Output**: The API must validate the LLM's response programmatically using Pydantic models before returning it to the caller. If validation fails, the system must trigger a single repair attempt or raise an explicit error.
