# Freeze Non-Editable Resume Fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict AI resume generation to only modify `summary` and `workExperience[*].description`; freeze all other fields (skills, education, personalProjects) to master resume values.

**Architecture:** Three defensive layers — (1) prompt constraints tell the LLM not to touch frozen fields, (2) post-LLM hard restoration unconditionally overwrites frozen fields with master values regardless of LLM output, (3) alignment validation logs when the LLM attempted to modify frozen fields for observability.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2. Tests run with `uv run pytest` from `apps/backend/`.

---

## File Map

| File | Change |
|---|---|
| `apps/backend/tests/test_preserve_fields.py` | **Create** — unit tests for Layer 2 |
| `apps/backend/tests/test_refiner_frozen_fields.py` | **Create** — unit tests for Layer 3 |
| `apps/backend/app/routers/resumes.py` | **Modify** — `_preserve_personal_info()` lines 193–208 |
| `apps/backend/app/services/refiner.py` | **Modify** — `validate_master_alignment()` lines 258–355, `fix_alignment_violations()` lines 462–535 |
| `apps/backend/app/prompts/templates.py` | **Modify** — 4 prompt strings + 2 `CRITICAL_TRUTHFULNESS_RULES` entries |
| `apps/backend/app/prompts/refinement.py` | **Modify** — `KEYWORD_INJECTION_PROMPT` lines 136–164 |

---

## Task 1: Layer 2 — Hard restoration of frozen fields

**Files:**
- Create: `apps/backend/tests/test_preserve_fields.py`
- Modify: `apps/backend/app/routers/resumes.py` (lines 193–208)

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_preserve_fields.py`:

```python
"""Tests for _preserve_personal_info frozen field restoration."""
from app.routers.resumes import _preserve_personal_info


def _base_original(extra: dict | None = None) -> dict:
    """Minimal original resume with valid personalInfo."""
    d = {"personalInfo": {"name": "Alice"}, "additional": {}}
    if extra:
        d.update(extra)
    return d


def test_freezes_skills_unconditionally() -> None:
    """Skills from master replace LLM output even when LLM returned valid-looking skills."""
    original = _base_original({"additional": {"technicalSkills": ["Python", "Django"]}})
    llm_output = {"personalInfo": {"name": "Alice"}, "additional": {"technicalSkills": ["Python", "React", "AWS"]}}
    result, _ = _preserve_personal_info(original, llm_output)
    assert result["additional"]["technicalSkills"] == ["Python", "Django"]


def test_freezes_skills_when_llm_returns_empty() -> None:
    """Skills from master replace empty LLM technicalSkills (replaces old conditional fallback)."""
    original = _base_original({"additional": {"technicalSkills": ["Python"]}})
    llm_output = {"personalInfo": {"name": "Alice"}, "additional": {"technicalSkills": []}}
    result, _ = _preserve_personal_info(original, llm_output)
    assert result["additional"]["technicalSkills"] == ["Python"]


def test_freezes_education() -> None:
    """Education from master replaces LLM-modified education."""
    original = _base_original({"education": [{"institution": "MIT", "degree": "B.S. CS", "years": "2014-2018"}]})
    llm_output = {
        "personalInfo": {"name": "Alice"},
        "additional": {},
        "education": [{"institution": "Harvard", "degree": "B.S. CS", "years": "2014-2018"}],
    }
    result, _ = _preserve_personal_info(original, llm_output)
    assert result["education"][0]["institution"] == "MIT"


def test_freezes_personal_projects() -> None:
    """PersonalProjects from master replaces LLM-modified projects."""
    original = _base_original({"personalProjects": [{"name": "MyApp", "role": "Creator"}]})
    llm_output = {
        "personalInfo": {"name": "Alice"},
        "additional": {},
        "personalProjects": [{"name": "AIApp", "role": "Creator"}],
    }
    result, _ = _preserve_personal_info(original, llm_output)
    assert result["personalProjects"][0]["name"] == "MyApp"


def test_empty_projects_restored_over_llm_additions() -> None:
    """Empty personalProjects list from master strips LLM-invented projects."""
    original = _base_original({"personalProjects": []})
    llm_output = {
        "personalInfo": {"name": "Alice"},
        "additional": {},
        "personalProjects": [{"name": "NewProject"}],
    }
    result, _ = _preserve_personal_info(original, llm_output)
    assert result["personalProjects"] == []


def test_absent_projects_in_master_leaves_llm_output_untouched() -> None:
    """If personalProjects is absent from master (None), LLM output is not touched."""
    original = _base_original()  # no personalProjects key
    llm_output = {
        "personalInfo": {"name": "Alice"},
        "additional": {},
        "personalProjects": [{"name": "NewProject"}],
    }
    result, _ = _preserve_personal_info(original, llm_output)
    # master had no field, so we don't freeze (LLM output preserved)
    assert result["personalProjects"] == [{"name": "NewProject"}]


def test_no_master_data_returns_llm_output_unchanged() -> None:
    """When original_data is None, returns improved_data as-is (existing behaviour)."""
    llm_output = {"personalInfo": {"name": "Alice"}, "additional": {"technicalSkills": ["AWS"]}}
    result, warnings = _preserve_personal_info(None, llm_output)
    assert result == llm_output
    assert len(warnings) > 0
```

- [ ] **Step 2: Run to confirm all 7 tests fail**

```bash
cd apps/backend && uv run pytest tests/test_preserve_fields.py -v
```

Expected: 7 FAILures (fields not yet frozen)

- [ ] **Step 3: Implement the Layer 2 changes**

In `apps/backend/app/routers/resumes.py`, find and replace the entire block at lines 193–202 (the conditional technicalSkills fallback):

```python
        # Populate technicalSkills from master if LLM returned empty
        improved_skills = result_additional.get("technicalSkills", [])
        if not improved_skills:
            original_skills = original_additional.get("technicalSkills", [])
            if original_skills:
                result_additional["technicalSkills"] = copy.deepcopy(original_skills)
                logger.info(
                    "technicalSkills empty in LLM output; populated %d from master",
                    len(original_skills),
                )
```

Replace with:

```python
        # Freeze technicalSkills unconditionally from master
        original_skills = original_additional.get("technicalSkills")
        if original_skills is not None:
            result_additional["technicalSkills"] = copy.deepcopy(original_skills)
            logger.info(
                "Froze technicalSkills from master (%d skills)", len(original_skills)
            )
```

Then insert the following block between the language-strip block (line 204–206) and the `return result, warnings` (line 208). The final code from line 204 onward should look like:

```python
    # Strip spoken languages from output (not relevant to resume tailoring)
    if isinstance(result.get("additional"), dict):
        result["additional"]["languages"] = []

    # Freeze education from master
    original_education = original_data.get("education")
    if original_education is not None:
        result["education"] = copy.deepcopy(original_education)
        logger.info("Froze education from master (%d entries)", len(original_education))

    # Freeze personalProjects from master
    original_projects = original_data.get("personalProjects")
    if original_projects is not None:
        result["personalProjects"] = copy.deepcopy(original_projects)
        logger.info(
            "Froze personalProjects from master (%d entries)", len(original_projects)
        )

    return result, warnings
```

- [ ] **Step 4: Run tests and confirm all 7 pass**

```bash
cd apps/backend && uv run pytest tests/test_preserve_fields.py -v
```

Expected: 7 PASSed

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd apps/backend && uv run pytest tests/ -v
```

Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add apps/backend/tests/test_preserve_fields.py apps/backend/app/routers/resumes.py
git commit -m "feat: freeze technicalSkills, education, personalProjects in _preserve_personal_info"
```

---

## Task 2: Layer 3 — Alignment validation for frozen fields

**Files:**
- Create: `apps/backend/tests/test_refiner_frozen_fields.py`
- Modify: `apps/backend/app/services/refiner.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/backend/tests/test_refiner_frozen_fields.py`:

```python
"""Tests for frozen-field alignment validation and fix logic."""
from app.services.refiner import fix_alignment_violations, validate_master_alignment
from app.schemas.refinement import AlignmentViolation


# ─── validate_master_alignment ────────────────────────────────────────────────

def test_skill_not_in_master_detected() -> None:
    master = {"additional": {"technicalSkills": ["Python"]}}
    tailored = {"additional": {"technicalSkills": ["Python", "AWS"]}}
    report = validate_master_alignment(tailored, master)
    types = [v.violation_type for v in report.violations]
    assert "skill_not_in_master" in types
    vals = [v.value for v in report.violations if v.violation_type == "skill_not_in_master"]
    assert "aws" in vals


def test_master_skill_missing_detected() -> None:
    master = {"additional": {"technicalSkills": ["Python", "Django"]}}
    tailored = {"additional": {"technicalSkills": ["Python"]}}
    report = validate_master_alignment(tailored, master)
    types = [v.violation_type for v in report.violations]
    assert "master_skill_missing" in types
    vals = [v.value for v in report.violations if v.violation_type == "master_skill_missing"]
    assert "django" in vals


def test_matching_skills_produce_no_skill_violations() -> None:
    master = {"additional": {"technicalSkills": ["Python", "Django"]}}
    tailored = {"additional": {"technicalSkills": ["python", "django"]}}  # case-insensitive
    report = validate_master_alignment(tailored, master)
    skill_types = {"skill_not_in_master", "master_skill_missing"}
    assert not any(v.violation_type in skill_types for v in report.violations)


def test_skill_violations_are_warning_severity() -> None:
    master = {"additional": {"technicalSkills": ["Python"]}}
    tailored = {"additional": {"technicalSkills": ["Python", "AWS"]}}
    report = validate_master_alignment(tailored, master)
    skill_violations = [v for v in report.violations if "skill" in v.violation_type]
    assert all(v.severity == "warning" for v in skill_violations)


def test_skill_violations_do_not_break_is_aligned() -> None:
    """Skill violations are warning-only and must not set is_aligned=False."""
    master = {"additional": {"technicalSkills": ["Python"]}}
    tailored = {"additional": {"technicalSkills": ["Python", "AWS"]}}
    report = validate_master_alignment(tailored, master)
    assert report.is_aligned is True


def test_education_entry_count_mismatch_detected() -> None:
    master = {"education": [{"institution": "MIT", "degree": "B.S. CS", "years": "2014-2018"}]}
    tailored = {"education": []}
    report = validate_master_alignment(tailored, master)
    types = [v.violation_type for v in report.violations]
    assert "education_entry_count_mismatch" in types


def test_education_field_modified_detected() -> None:
    master = {"education": [{"institution": "MIT", "degree": "B.S. CS", "years": "2014-2018"}]}
    tailored = {"education": [{"institution": "Harvard", "degree": "B.S. CS", "years": "2014-2018"}]}
    report = validate_master_alignment(tailored, master)
    types = [v.violation_type for v in report.violations]
    assert "education_field_modified" in types


def test_education_count_mismatch_skips_per_field_checks() -> None:
    """When entry counts differ, no per-field violations are emitted."""
    master = {"education": [{"institution": "MIT", "degree": "B.S. CS", "years": "2014-2018"}]}
    tailored = {"education": []}
    report = validate_master_alignment(tailored, master)
    assert not any(v.violation_type == "education_field_modified" for v in report.violations)


def test_project_entry_count_mismatch_detected() -> None:
    master = {"personalProjects": [{"name": "MyApp"}]}
    tailored = {"personalProjects": []}
    report = validate_master_alignment(tailored, master)
    types = [v.violation_type for v in report.violations]
    assert "project_entry_count_mismatch" in types


def test_new_violations_are_all_warning() -> None:
    master = {
        "additional": {"technicalSkills": ["Python"]},
        "education": [{"institution": "MIT", "degree": "B.S.", "years": "2014-2018"}],
        "personalProjects": [{"name": "App"}],
    }
    tailored = {
        "additional": {"technicalSkills": ["Python", "AWS"]},
        "education": [],
        "personalProjects": [],
    }
    report = validate_master_alignment(tailored, master)
    new_types = {
        "skill_not_in_master", "master_skill_missing",
        "education_entry_count_mismatch", "education_field_modified",
        "project_entry_count_mismatch",
    }
    new_violations = [v for v in report.violations if v.violation_type in new_types]
    assert len(new_violations) > 0
    assert all(v.severity == "warning" for v in new_violations)
    assert report.is_aligned is True  # no critical violations


# ─── fix_alignment_violations ─────────────────────────────────────────────────

def test_fix_restores_skills_from_master() -> None:
    master = {"additional": {"technicalSkills": ["Python", "Django"]}}
    tailored = {"additional": {"technicalSkills": ["Python", "AWS"]}}
    violations = [
        AlignmentViolation(
            field_path="additional.technicalSkills",
            violation_type="skill_not_in_master",
            value="aws",
            severity="warning",
        )
    ]
    fixed = fix_alignment_violations(tailored, violations, master)
    assert set(fixed["additional"]["technicalSkills"]) == {"Python", "Django"}


def test_fix_restores_education_from_master() -> None:
    master = {"education": [{"institution": "MIT", "degree": "B.S. CS"}]}
    tailored = {"education": [{"institution": "Harvard", "degree": "B.S. CS"}]}
    violations = [
        AlignmentViolation(
            field_path="education[0].institution",
            violation_type="education_field_modified",
            value="mit -> harvard",
            severity="warning",
        )
    ]
    fixed = fix_alignment_violations(tailored, violations, master)
    assert fixed["education"][0]["institution"] == "MIT"


def test_fix_restores_projects_from_master() -> None:
    master = {"personalProjects": [{"name": "Original"}]}
    tailored = {"personalProjects": []}
    violations = [
        AlignmentViolation(
            field_path="personalProjects",
            violation_type="project_entry_count_mismatch",
            value="1 -> 0",
            severity="warning",
        )
    ]
    fixed = fix_alignment_violations(tailored, violations, master)
    assert len(fixed["personalProjects"]) == 1
    assert fixed["personalProjects"][0]["name"] == "Original"


def test_fix_restores_skills_only_once_for_multiple_violations() -> None:
    """Multiple skill violations restore the skills array only once (idempotent)."""
    master = {"additional": {"technicalSkills": ["Python"]}}
    tailored = {"additional": {"technicalSkills": ["Python", "AWS", "GCP"]}}
    violations = [
        AlignmentViolation(
            field_path="additional.technicalSkills",
            violation_type="skill_not_in_master",
            value="aws",
            severity="warning",
        ),
        AlignmentViolation(
            field_path="additional.technicalSkills",
            violation_type="skill_not_in_master",
            value="gcp",
            severity="warning",
        ),
    ]
    fixed = fix_alignment_violations(tailored, violations, master)
    assert fixed["additional"]["technicalSkills"] == ["Python"]
```

- [ ] **Step 2: Run to confirm all 15 tests fail**

```bash
cd apps/backend && uv run pytest tests/test_refiner_frozen_fields.py -v
```

Expected: 15 FAILures

- [ ] **Step 3: Update `validate_master_alignment()` in `apps/backend/app/services/refiner.py`**

Find the comment block at lines 258–259:
```python
    # Note: technicalSkills are NOT checked - we intentionally allow adding
    # JD-relevant skills that aren't in the master resume.
```

Replace it with:
```python
    # technicalSkills are now checked — skills are frozen to master values.
    # Violations are warning severity (Layer 2 in the router guarantees restoration).
    tailored_skills = set(
        s.lower()
        for s in tailored.get("additional", {}).get("technicalSkills", [])
        if isinstance(s, str)
    )
    master_skills = set(
        s.lower()
        for s in master.get("additional", {}).get("technicalSkills", [])
        if isinstance(s, str)
    )
    for skill in tailored_skills - master_skills:
        violations.append(
            AlignmentViolation(
                field_path="additional.technicalSkills",
                violation_type="skill_not_in_master",
                value=skill,
                severity="warning",
            )
        )
    for skill in master_skills - tailored_skills:
        violations.append(
            AlignmentViolation(
                field_path="additional.technicalSkills",
                violation_type="master_skill_missing",
                value=skill,
                severity="warning",
            )
        )
```

Then, after the existing work-experience checks (just before the `is_aligned = ...` line at the end of `validate_master_alignment`), add:

```python
    # Check education alignment (index-based comparison)
    master_edu = master.get("education", [])
    tailored_edu = tailored.get("education", [])
    if len(master_edu) != len(tailored_edu):
        violations.append(
            AlignmentViolation(
                field_path="education",
                violation_type="education_entry_count_mismatch",
                value=f"{len(master_edu)} -> {len(tailored_edu)}",
                severity="warning",
            )
        )
    else:
        for i, (m_entry, t_entry) in enumerate(zip(master_edu, tailored_edu)):
            if not isinstance(m_entry, dict) or not isinstance(t_entry, dict):
                continue
            for field in ("institution", "degree", "years"):
                m_val = m_entry.get(field, "").lower().strip()
                t_val = t_entry.get(field, "").lower().strip()
                if m_val and t_val and m_val != t_val:
                    violations.append(
                        AlignmentViolation(
                            field_path=f"education[{i}].{field}",
                            violation_type="education_field_modified",
                            value=f"{m_val} -> {t_val}",
                            severity="warning",
                        )
                    )

    # Check personalProjects alignment (count only)
    master_proj = master.get("personalProjects", [])
    tailored_proj = tailored.get("personalProjects", [])
    if len(master_proj) != len(tailored_proj):
        violations.append(
            AlignmentViolation(
                field_path="personalProjects",
                violation_type="project_entry_count_mismatch",
                value=f"{len(master_proj)} -> {len(tailored_proj)}",
                severity="warning",
            )
        )
```

- [ ] **Step 4: Update `fix_alignment_violations()` in `apps/backend/app/services/refiner.py`**

Find the loop at line 491:
```python
    for violation in violations:
        if violation.severity != "critical":
            continue
```

Replace the `continue` guard with logic that handles both critical and warning violations. Add tracking sets before the loop, and new `elif` branches after the existing critical handlers:

```python
    # Track which warning restorations have been applied (restore once per pass)
    _skills_restored = False
    _education_restored = False
    _projects_restored = False

    for violation in violations:
        if violation.severity == "critical":
            if violation.violation_type == "fabricated_cert":
                certs = fixed.get("additional", {}).get("certificationsTraining", [])
                fixed.setdefault("additional", {})["certificationsTraining"] = [
                    c for c in certs if c.lower() != violation.value.lower()
                ]

            elif violation.violation_type == "fabricated_company":
                logger.error("Critical: Fabricated company detected: %s", violation.value)
                if "workExperience" in fixed:
                    fixed["workExperience"] = [
                        exp
                        for exp in fixed["workExperience"]
                        if exp.get("company", "").lower() != violation.value.lower()
                    ]
                    logger.info(
                        "Removed fabricated company '%s' from resume",
                        violation.value,
                    )

            elif violation.violation_type == "modified_title":
                company_key = violation.field_path.split("[")[1].split("]")[0]
                master_exp = master_by_company.get(company_key)
                if master_exp:
                    for exp in fixed.get("workExperience", []):
                        if exp.get("company", "").lower() == company_key:
                            exp["title"] = master_exp.get("title", exp.get("title", ""))
                            logger.info("Restored title for '%s'", company_key)

            elif violation.violation_type == "modified_dates":
                company_key = violation.field_path.split("[")[1].split("]")[0]
                master_exp = master_by_company.get(company_key)
                if master_exp:
                    for exp in fixed.get("workExperience", []):
                        if exp.get("company", "").lower() == company_key:
                            exp["years"] = master_exp.get("years", exp.get("years", ""))
                            logger.info("Restored dates for '%s'", company_key)

        elif violation.severity == "warning":
            if violation.violation_type in ("skill_not_in_master", "master_skill_missing"):
                if not _skills_restored and master:
                    master_skills = master.get("additional", {}).get("technicalSkills")
                    if master_skills is not None:
                        fixed.setdefault("additional", {})["technicalSkills"] = copy.deepcopy(master_skills)
                        logger.info("Restored technicalSkills from master after warning violation")
                        _skills_restored = True

            elif violation.violation_type in ("education_entry_count_mismatch", "education_field_modified"):
                if not _education_restored and master:
                    master_edu = master.get("education")
                    if master_edu is not None:
                        fixed["education"] = copy.deepcopy(master_edu)
                        logger.info("Restored education from master after warning violation")
                        _education_restored = True

            elif violation.violation_type == "project_entry_count_mismatch":
                if not _projects_restored and master:
                    master_proj = master.get("personalProjects")
                    if master_proj is not None:
                        fixed["personalProjects"] = copy.deepcopy(master_proj)
                        logger.info("Restored personalProjects from master after warning violation")
                        _projects_restored = True
```

Note: this replaces the existing loop body entirely. The old code filtered `if violation.severity != "critical": continue` — the new version handles both severities explicitly in `if/elif` branches.

- [ ] **Step 5: Run Layer 3 tests to confirm all 15 pass**

```bash
cd apps/backend && uv run pytest tests/test_refiner_frozen_fields.py -v
```

Expected: 15 PASSed

- [ ] **Step 6: Run full suite to check for regressions**

```bash
cd apps/backend && uv run pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add apps/backend/tests/test_refiner_frozen_fields.py apps/backend/app/services/refiner.py
git commit -m "feat: add frozen-field alignment validation and fix logic in refiner"
```

---

## Task 3: Layer 1 — Prompt constraints

**Files:**
- Modify: `apps/backend/app/prompts/templates.py`
- Modify: `apps/backend/app/prompts/refinement.py`

No unit tests needed for prompt strings. Correctness is enforced by Layers 2 and 3.

- [ ] **Step 1: Update `IMPROVE_RESUME_PROMPT_FULL` in `templates.py`**

Find the `SKILLS STRATEGY` section (around lines 262–265):
```
SKILLS STRATEGY:
- ADD ALL relevant skills and tools from the job description to technicalSkills, even if not in the original resume
- Include required_skills first, then preferred_skills, then other JD keywords
- ALWAYS include a comprehensive technicalSkills section aligned with the JD
```

Replace the entire `SKILLS STRATEGY` block with:
```
FROZEN FIELDS (copy these EXACTLY from the original resume — do NOT modify):
- technicalSkills: copy as-is, do not add or remove any skills
- education: copy all entries as-is, do not change any field
- personalProjects: copy all entries as-is, do not change any field
```

- [ ] **Step 2: Update `IMPROVE_RESUME_PROMPT_BOOST` in `templates.py`**

Find the rules (around lines 304–305):
```
- ADD any missing JD skills and tools to the technicalSkills list
- ALWAYS include a technicalSkills section with relevant skills from the job description
```

Remove both lines. Then find the `DO NOT modify...` line in the BOOST prompt (near line 311) and insert the FROZEN FIELDS block immediately before it as a new named section:

```
FROZEN FIELDS (copy these EXACTLY from the original resume — do NOT modify):
- technicalSkills: copy as-is, do not add or remove any skills
- education: copy all entries as-is, do not change any field
- personalProjects: copy all entries as-is, do not change any field
```

- [ ] **Step 3: Update `CRITICAL_TRUTHFULNESS_RULES` in `templates.py`**

In `CRITICAL_TRUTHFULNESS_RULES["full"]` (around line 161), remove:
```
"ADD ALL relevant skills and tools from the job description to the technicalSkills section, even if not in the original resume. "
```

In `CRITICAL_TRUTHFULNESS_RULES["boost"]` (around line 166), remove:
```
"You MAY freely add relevant skills and tools from the job description to the skills section. "
```

- [ ] **Step 4: Add FROZEN FIELDS block to `IMPROVE_RESUME_PROMPT_NUDGE` and `IMPROVE_RESUME_PROMPT_KEYWORDS`**

Both prompts already say not to add new tools/skills, but add the explicit `FROZEN FIELDS` block to each for consistency. Insert it into the `Rules:` section of each prompt:

```
FROZEN FIELDS (copy these EXACTLY from the original resume — do NOT modify):
- technicalSkills: copy as-is, do not add or remove any skills
- education: copy all entries as-is, do not change any field
- personalProjects: copy all entries as-is, do not change any field
```

- [ ] **Step 5: Update `KEYWORD_INJECTION_PROMPT` in `refinement.py`**

Find the `STRATEGY` numbered list (lines 138–143):
```
STRATEGY:
1. ADD ALL skills and tools from the keywords list to the technicalSkills section
2. Rewrite bullet points to incorporate keywords, mirroring JD phrasing where possible
3. You MAY add new bullet points if needed to incorporate remaining keywords
4. You MAY add keywords that are NOT in the master resume - the JD is the source of truth for what skills to include
5. Invent realistic metrics and details to support keyword integration
```

Remove items 1 and 4. Renumber the remaining items (2→1, 3→2, 5→3). Add the FROZEN FIELDS block to the `CONSTRAINTS` section:

```
STRATEGY:
1. Rewrite bullet points to incorporate keywords, mirroring JD phrasing where possible
2. You MAY add new bullet points if needed to incorporate remaining keywords
3. Invent realistic metrics and details to support keyword integration

CONSTRAINTS:
1. FROZEN FIELDS (copy these EXACTLY from the original resume — do NOT modify):
   - technicalSkills: copy as-is, do not add or remove any skills
   - education: copy all entries as-is, do not change any field
   - personalProjects: copy all entries as-is, do not change any field
2. Do NOT modify certifications - copy certificationsTraining exactly as-is from the master resume
3. Do NOT include spoken languages - set languages to an empty array []
4. Keep company names, job titles, and dates unchanged from the current tailored resume
5. Maintain the exact same JSON structure
6. Do not use em-dashes (—) or their variants (---, --)
```

- [ ] **Step 6: Run the full test suite**

```bash
cd apps/backend && uv run pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/prompts/templates.py apps/backend/app/prompts/refinement.py
git commit -m "feat: add frozen fields constraints to all LLM prompt templates"
```

---

## Task 4: Final verification

- [ ] **Step 1: Run the complete test suite one final time**

```bash
cd apps/backend && uv run pytest tests/ -v
```

Expected: all tests pass, no errors

- [ ] **Step 2: Restart the dev server to clear Python bytecode caches**

```bash
bash scripts/restart-dev.sh
```

- [ ] **Step 3: Final commit (if any loose files)**

```bash
cd apps/backend && git status
# If anything unstaged:
git add -p
git commit -m "chore: freeze non-editable resume fields complete"
```
