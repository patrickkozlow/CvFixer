# Freeze Non-Editable Resume Fields

**Date:** 2026-03-23
**Status:** Approved

---

## Problem

When generating a tailored resume, the AI is currently permitted to:
- Add or remove items from `technicalSkills`
- Rewrite `education` entries
- Rewrite `personalProjects` entries

The `full` and `boost` prompts actively instruct the LLM to *add* skills from the job description. No post-processing step protects these fields.

The user wants generation to touch only:
- `summary` — full rewrite allowed
- `workExperience[*].description` — bullet point rewrites allowed

All other fields must be frozen to their master resume values.

---

## Fields That Must Be Frozen

| Field | Current state | Target state |
|---|---|---|
| `personalInfo` | ✅ Already frozen (restored post-LLM) | No change |
| `additional.certificationsTraining` | ✅ Already frozen (restored post-LLM) | No change |
| `workExperience[*].title` | ✅ Already validated + restored | No change |
| `workExperience[*].company` | ✅ Already validated + restored | No change |
| `workExperience[*].years` | ✅ Already validated + restored | No change |
| `additional.technicalSkills` | ❌ LLM actively adds skills | Freeze |
| `education` | ❌ Unprotected | Freeze |
| `personalProjects` | ❌ Unprotected | Freeze |

Fields that remain changeable: `summary`, `workExperience[*].description`.

---

## Solution: Three Defensive Layers

### Layer 1 — Prompt Constraints

**Files:** `apps/backend/app/prompts/templates.py`, `apps/backend/app/prompts/refinement.py`

Add a `FROZEN FIELDS` constraint block to all five prompt templates:
- `IMPROVE_RESUME_PROMPT_NUDGE`
- `IMPROVE_RESUME_PROMPT_KEYWORDS`
- `IMPROVE_RESUME_PROMPT_FULL`
- `IMPROVE_RESUME_PROMPT_BOOST`
- `KEYWORD_INJECTION_PROMPT`

The constraint block reads:

```
FROZEN FIELDS (copy these EXACTLY from the original resume — do NOT modify):
- technicalSkills: copy as-is, do not add or remove any skills
- education: copy all entries as-is, do not change any field
- personalProjects: copy all entries as-is, do not change any field
```

**Specific strings to remove in `templates.py`:**

In `IMPROVE_RESUME_PROMPT_FULL` (SKILLS STRATEGY section):
- Remove: `"ADD ALL relevant skills and tools from the job description to technicalSkills, even if not in the original resume"`
- Remove: `"Include required_skills first, then preferred_skills, then other JD keywords"`
- Remove: `"ALWAYS include a comprehensive technicalSkills section aligned with the JD"`
- Replace the entire SKILLS STRATEGY section with the FROZEN FIELDS block.

In `IMPROVE_RESUME_PROMPT_BOOST`:
- Remove: `"ADD any missing JD skills and tools to the technicalSkills list"`
- Remove: `"ALWAYS include a technicalSkills section with relevant skills from the job description"`
- Replace with the FROZEN FIELDS block.

In `CRITICAL_TRUTHFULNESS_RULES["full"]`:
- Remove: `"ADD ALL relevant skills and tools from the job description to the technicalSkills section, even if not in the original resume."`

In `CRITICAL_TRUTHFULNESS_RULES["boost"]`:
- Remove: `"You MAY freely add relevant skills and tools from the job description to the skills section."`

**Specific strings to remove in `refinement.py`:**

In `KEYWORD_INJECTION_PROMPT`:
- Remove the numbered instruction: `"1. ADD ALL skills and tools from the keywords list to the technicalSkills section"`
- Remove: `"4. You MAY add keywords that are NOT in the master resume - the JD is the source of truth for what skills to include"`
- Add the FROZEN FIELDS block to the CONSTRAINTS section.
- Renumber remaining strategy steps.

### Layer 2 — Hard Restoration (Post-LLM)

**File:** `apps/backend/app/routers/resumes.py`

Extend `_preserve_personal_info()` to unconditionally restore three additional fields from master after every LLM call. Replace the existing conditional `technicalSkills` fallback (which only populates when empty) with an unconditional restoration:

```python
# Freeze technicalSkills unconditionally from master
original_skills = original_additional.get("technicalSkills")
if original_skills is not None:
    result_additional["technicalSkills"] = copy.deepcopy(original_skills)

# Freeze education from master
original_education = original_data.get("education")
if original_education is not None:
    result["education"] = copy.deepcopy(original_education)

# Freeze personalProjects from master
original_projects = original_data.get("personalProjects")
if original_projects is not None:
    result["personalProjects"] = copy.deepcopy(original_projects)
```

The existing conditional block (`if not improved_skills: ...`) is removed and replaced by the unconditional freeze above.

This function runs after every LLM call and after refinement — it is the authoritative guarantee. Even if the LLM ignores Layer 1 instructions, Layer 2 will always restore the correct values.

### Layer 3 — Alignment Validation + Fix

**File:** `apps/backend/app/services/refiner.py`

Extend `validate_master_alignment()` to detect and log the following new violation types (all with severity `"warning"`):

**Skill violations** (set-based comparison, case-insensitive):
- `"skill_not_in_master"` — a skill appears in tailored that is not in master (one violation per extra skill)
- `"master_skill_missing"` — a master skill is absent from tailored (one violation per missing skill)
- Also update the comment on line 258-259 in `refiner.py` that currently says "technicalSkills are NOT checked" — replace it with a comment explaining skills are now checked and frozen.

**Education violations** (index-based comparison — compare entry at position 0 to position 0, etc.):
- `"education_entry_count_mismatch"` — entry count differs from master; log once, skip per-field checks
- `"education_field_modified"` — one of `institution`, `degree`, or `years` differs at the same index vs. master (one violation per changed field, using `.lower().strip()` comparison)

**PersonalProject violations** (count-only; no per-field comparison needed):
- `"project_entry_count_mismatch"` — entry count differs from master; log once

All violations use severity `"warning"` (not `"critical"`) because Layer 2 already guarantees correctness. Layer 3 exists purely for observability — to log when the LLM attempts to modify frozen fields.

Extend `fix_alignment_violations()` to also process `"warning"` severity violations (currently it only processes `"critical"` at the top of the loop). For the new violation types, restoration logic is:
- Any skill violation (`skill_not_in_master` or `master_skill_missing`) → restore `additional.technicalSkills` from master (restore once; skip if already restored this pass)
- Any education violation → restore entire `education` array from master (once per pass)
- `project_entry_count_mismatch` → restore entire `personalProjects` array from master (once per pass)

**Layer 2 logging:** Add `logger.info` calls in `_preserve_personal_info()` when each frozen field is restored (consistent with existing logging for `technicalSkills` fallback at line 199).

---

## What Changes and What Does Not

**Changes:**
- `apps/backend/app/prompts/templates.py` — update 4 prompts + `CRITICAL_TRUTHFULNESS_RULES["full"]` and `["boost"]`
- `apps/backend/app/prompts/refinement.py` — update `KEYWORD_INJECTION_PROMPT` (remove skill-injection steps 1 and 4, add frozen fields constraint)
- `apps/backend/app/routers/resumes.py` — extend `_preserve_personal_info()`: replace conditional skills fallback with unconditional freeze for skills, education, personalProjects
- `apps/backend/app/services/refiner.py` — extend `validate_master_alignment()` with 5 new warning violations; extend `fix_alignment_violations()` to process warning-severity violations

**Does not change:**
- Resume schema (Pydantic models)
- API contracts — no request/response shape changes
- Frontend
- Database
- Test suite

---

## Edge Cases

- **No master resume available:** `_preserve_personal_info()` already returns early with a warning if `original_data` is None. Frozen fields will not be restored in this case.
- **User has no personalProjects:** If the field is absent from master, it will remain absent after Layer 2. If it is an empty array, it will be restored as an empty array.
- **LLM adds new education or project entries:** Layer 2 replaces the entire array with master values, removing any new entries the LLM invented.
- **LLM returns empty technicalSkills:** Previously handled by a conditional fallback that only populated when empty. The new unconditional freeze supersedes this — master skills are always restored regardless.
- **Layer 3 vs Layer 2 interaction:** Layer 3 validation runs inside `refine_resume()`, which is called before `_preserve_personal_info()`. Violations detected by Layer 3 represent LLM output before Layer 2 restoration and are valuable for observability even though Layer 2 will correct them.
