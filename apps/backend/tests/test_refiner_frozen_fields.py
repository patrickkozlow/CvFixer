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
