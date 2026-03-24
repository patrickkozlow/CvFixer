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
