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

The `full` and `boost` prompts currently contain "ADD ALL relevant skills and tools from the job description to technicalSkills" — this instruction is removed and replaced with the freeze constraint.

The `KEYWORD_INJECTION_PROMPT` currently contains "ADD ALL skills and tools from the keywords list to the technicalSkills section" — this instruction is removed and the frozen fields block is added.

The `CRITICAL_TRUTHFULNESS_RULES` for `full` and `boost` modes also contain skill-addition language that must be removed.

### Layer 2 — Hard Restoration (Post-LLM)

**File:** `apps/backend/app/routers/resumes.py`

Extend `_preserve_personal_info()` to restore three additional fields from the master resume after every LLM call:

```python
# Freeze technicalSkills from master
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

This runs after every LLM call and after refinement. It is the authoritative guarantee — Layer 1 guides the LLM, but Layer 2 ensures correctness regardless of LLM output.

Note: The existing fallback that populates `technicalSkills` from master when the LLM returns an empty list is superseded by the freeze — the field is always restored from master unconditionally.

### Layer 3 — Alignment Validation + Fix

**File:** `apps/backend/app/services/refiner.py`

Extend `validate_master_alignment()` to detect:

1. **Skill violations** — any skill in the tailored resume not in master, or any master skill missing from tailored. Severity: `"warning"`.
2. **Education violations** — entry count mismatch or any field change (`institution`, `degree`, `years`) vs. master. Severity: `"warning"`.
3. **PersonalProject violations** — entry count mismatch vs. master. Severity: `"warning"`.

Extend `fix_alignment_violations()` with corresponding fix logic that restores the affected field from master.

Violations are `"warning"` severity (not `"critical"`) because Layer 2 already guarantees correctness. The validation layer exists for observability — to log how often the LLM attempts to modify frozen fields.

---

## What Changes and What Does Not

**Changes:**
- `apps/backend/app/prompts/templates.py` — update 4 prompts + `CRITICAL_TRUTHFULNESS_RULES`
- `apps/backend/app/prompts/refinement.py` — update `KEYWORD_INJECTION_PROMPT`
- `apps/backend/app/routers/resumes.py` — extend `_preserve_personal_info()`
- `apps/backend/app/services/refiner.py` — extend `validate_master_alignment()` and `fix_alignment_violations()`

**Does not change:**
- Resume schema (Pydantic models)
- API contracts — no request/response shape changes
- Frontend
- Database
- Test suite

---

## Edge Cases

- **No master resume available:** `_preserve_personal_info()` already handles this — it returns early with a warning if `original_data` is None. Frozen fields will not be restored in this case, which is the existing behavior for personal info.
- **User has no personalProjects:** Field is either absent or an empty list. Restoring an empty list is a no-op; absent field is left absent.
- **LLM returns empty technicalSkills:** Previously, there was a fallback to populate from master only when empty. With the freeze, the field is always restored from master unconditionally, which subsumes the old fallback.
