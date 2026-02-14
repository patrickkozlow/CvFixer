"""LLM prompt templates for resume processing."""

# Language code to full name mapping
LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "pt": "Brazilian Portuguese",
}


def get_language_name(code: str) -> str:
    """Get full language name from code."""
    return LANGUAGE_NAMES.get(code, "English")


# Schema with example values - used for prompts to show LLM expected format
RESUME_SCHEMA_EXAMPLE = """{
  "personalInfo": {
    "name": "John Doe",
    "title": "Software Engineer",
    "email": "john@example.com",
    "phone": "+1-555-0100",
    "location": "San Francisco, CA",
    "website": "https://johndoe.dev",
    "linkedin": "linkedin.com/in/johndoe",
    "github": "github.com/johndoe"
  },
  "summary": "Experienced software engineer with 5+ years...",
  "workExperience": [
    {
      "id": 1,
      "title": "Senior Software Engineer",
      "company": "Tech Corp",
      "location": "San Francisco, CA",
      "years": "2020 - Present",
      "description": [
        "Led development of microservices architecture",
        "Improved system performance by 40%"
      ]
    }
  ],
  "education": [
    {
      "id": 1,
      "institution": "University of California",
      "degree": "B.S. Computer Science",
      "years": "2014 - 2018",
      "description": "Graduated with honors"
    }
  ],
  "personalProjects": [
    {
      "id": 1,
      "name": "Open Source Tool",
      "role": "Creator & Maintainer",
      "years": "2021 - Present",
      "description": [
        "Built CLI tool with 1000+ GitHub stars",
        "Used by 50+ companies worldwide"
      ]
    }
  ],
  "additional": {
    "technicalSkills": ["Python", "JavaScript", "AWS", "Docker"],
    "languages": ["English (Native)", "Spanish (Conversational)"],
    "certificationsTraining": ["AWS Solutions Architect"],
    "awards": ["Employee of the Year 2022"]
  },
  "customSections": {
    "publications": {
      "sectionType": "itemList",
      "items": [
        {
          "id": 1,
          "title": "Paper Title",
          "subtitle": "Journal Name",
          "years": "2023",
          "description": ["Brief description of the publication"]
        }
      ]
    },
    "volunteer_work": {
      "sectionType": "text",
      "text": "Description of volunteer activities..."
    }
  }
}"""

PARSE_RESUME_PROMPT = """Parse this resume into JSON. Output ONLY the JSON object, no other text.

Map content to standard sections when possible. For non-standard sections (like Publications, Volunteer Work, Research, Hobbies), add them to customSections with an appropriate type.

Example output format:
{schema}

Custom section types:
- "text": Single text block (e.g., objective, statement)
- "itemList": List of items with title, subtitle, years, description (e.g., publications, research)
- "stringList": Simple list of strings (e.g., hobbies, interests)

Rules:
- Use "" for missing text fields, [] for missing arrays, null for optional fields
- Number IDs starting from 1
- Format years as "YYYY - YYYY" or "YYYY - Present"
- Use snake_case for custom section keys (e.g., "volunteer_work", "publications")
- Preserve the original section name as a descriptive key
- Normalize dates: "Jan 2020" → "2020", "2020-2021" → "2020 - 2021", "Current"/"Ongoing" → "Present"
- For ambiguous dates like "3 years experience", infer approximate years from context or use "~YYYY"
- Flag overlapping dates (concurrent roles) by preserving both, don't merge

Resume to parse:
{resume_text}"""

EXTRACT_KEYWORDS_PROMPT = """Extract job requirements as JSON. Output ONLY the JSON object, no other text.

Example format:
{{
  "required_skills": ["Python", "AWS"],
  "preferred_skills": ["Kubernetes"],
  "experience_requirements": ["5+ years"],
  "education_requirements": ["Bachelor's in CS"],
  "key_responsibilities": ["Lead team"],
  "keywords": ["microservices", "agile"],
  "experience_years": 5,
  "seniority_level": "senior"
}}

Extract numeric years (e.g., "5+ years" → 5) and infer seniority level.

Job description:
{job_description}"""

CRITICAL_TRUTHFULNESS_RULES_TEMPLATE = """CRITICAL TRUTHFULNESS RULES - NEVER VIOLATE:
1. DO NOT add company names not in the original source
2. DO NOT upgrade experience level (e.g., changing "Junior" to "Senior")
3. DO NOT extend employment dates or change timelines (Start/End dates must remain exact)
5. Job Designations/Titles MAY be optimized for keyword alignment, but Company Name and Duration must be preserved exactly
6. Publications/Research titles MAY be adjusted for relevance, but the underlying subject matter must remain relevant to the job description
7. {rule_7}

Violation of these rules could cause serious problems for the candidate in job interviews.
"""


def _build_truthfulness_rules(rule_7: str) -> str:
    return CRITICAL_TRUTHFULNESS_RULES_TEMPLATE.format(rule_7=rule_7)


CRITICAL_TRUTHFULNESS_RULES = {
    "nudge": _build_truthfulness_rules(
        "DO NOT add new bullet points or content - only rephrase existing content"
    ),
    "keywords": _build_truthfulness_rules(
        "You may rephrase existing bullet points to include keywords, but do NOT add new bullet points"
    ),
    "full": _build_truthfulness_rules(
        "You may expand existing bullet points or add new ones that elaborate on existing work, but DO NOT invent entirely new responsibilities"
    ),
    "Custom": _build_truthfulness_rules(
        "You ARE PERMITTED to add relevant technical skills from the Job Description. "
        "You ARE PERMITTED to fabricate realistic quantitative metrics (percentages, team sizes, dollar amounts) to strengthen bullet points. "
        "You MUST keep all certifications and professional designations exactly as they appear in the original. "
        "You MUST NOT add languages spoken, hobbies, interests, or references sections."
    ),
}

IMPROVE_RESUME_PROMPT_NUDGE = """Lightly nudge this resume toward the job description. Output ONLY the JSON object, no other text.

{critical_truthfulness_rules}

IMPORTANT: Generate ALL text content (summary, descriptions, skills) in {output_language}.

Rules:
- Make minimal, conservative edits only where there is a clear existing match
- Do NOT change the candidate's role, industry, or seniority level
- Do NOT introduce new tools, technologies, or certifications not already present
- Do NOT add new bullet points or sections
- Preserve original bullet count and ordering within each section
- Keep proper nouns (names, company names, locations) unchanged
- Preserve the structure of any customSections from the original resume
- Preserve original date ranges exactly - do not modify years
- If the resume is non-technical, do NOT add technical jargon
- Do NOT use em dash ("—") anywhere in the writing/output, even if it exists, remove it

Job Description:
{job_description}

Keywords to emphasize (only if already supported by resume content):
{job_keywords}

Original Resume:
{original_resume}

Output in this JSON format:
{schema}"""

IMPROVE_RESUME_PROMPT_KEYWORDS = """Enhance this resume with relevant keywords from the job description. Output ONLY the JSON object, no other text.

{critical_truthfulness_rules}

IMPORTANT: Generate ALL text content (summary, descriptions, skills) in {output_language}.

Rules:
- Strengthen alignment by weaving in relevant keywords where evidence already exists
- You may rephrase bullet points to include keyword phrasing
- Do NOT introduce new skills, tools, or certifications not in the resume
- Do NOT change role, industry, or seniority level
- Preserve the structure of any customSections from the original resume
- Preserve original date ranges exactly - do not modify years
- If resume is non-technical, keep language non-technical while still aligning keywords
- Do NOT use em dash ("—") anywhere in the writing/output, even if it exists, remove it

Job Description:
{job_description}

Keywords to emphasize:
{job_keywords}

Original Resume:
{original_resume}

Output in this JSON format:
{schema}"""

IMPROVE_RESUME_PROMPT_FULL = """Tailor this resume for the job. Output ONLY the JSON object, no other text.

{critical_truthfulness_rules}

IMPORTANT: Generate ALL text content (summary, descriptions, skills) in {output_language}.

Rules:
- Rephrase content to highlight relevant experience
- DO NOT invent new information
- Use action verbs and quantifiable achievements
- Keep proper nouns (names, company names, locations) unchanged
- Translate job titles, descriptions, and skills to {output_language}
- Preserve the structure of any customSections from the original resume
- Improve custom section content the same way as standard sections
- Preserve original date ranges exactly - do not modify years
- Calculate and emphasize total relevant experience duration when it matches requirements
- Do NOT use em dash ("—") anywhere in the writing/output, even if it exists, remove it

Job Description:
{job_description}

Keywords to emphasize:
{job_keywords}

Original Resume:
{original_resume}

Output in this JSON format:
{schema}"""

IMPROVE_RESUME_PROMPT_CUSTOM = """Tailor this resume for the job. Output ONLY the JSON object, no other text.

{critical_truthfulness_rules}

IMPORTANT: Generate ALL text content (summary, descriptions, skills) in {output_language}.

Rules:
- Rephrase content to highlight relevant experience aligned with the Job Description
- **SKILLS STRATEGY: You MUST identify and add missing technical skills/tools from the Job Description to the 'Technical Skills' list.** Keep ALL existing skills and APPEND new relevant ones.
- Do ADD skills, technologies which are not in the master resume but necessary and relevant to the job description and job role
- Incorporate all necessary keywords meaningfully throughout
- Use action verbs and quantifiable achievements
- **METRICS STRATEGY: EVERY bullet point MUST include at least one quantitative metric (percentage improvement, team size, dollar amount, time saved, users impacted). Fabricate realistic metrics where the original has none. Base metrics on role seniority and industry norms.**
- Keep proper nouns (names, company names, locations) unchanged
- Translate job titles, descriptions, and skills to {output_language}
- Experience designation can be changed to align with Job Description, but keep Company Name and Duration UNCHANGED
- Each experience entry bullet point must be at MAX 600 characters long
- Each experience entry must have exactly 4 bullet points
- Each project description must be at least 400 characters long and be deeply relevant to job description. There should only be ONE bullet point for each project, but it should be comprehensive and detailed.
- Adjust and rename paper publications or research if necessary to align with the job
- Add more relevant technical skills in the Technical Skills section based on the Job Description
- In Summary section, explicitly mention experience duration
- **CERTIFICATIONS: DO NOT modify, add, or remove ANY certifications or professional designations. Copy the certificationsTraining array exactly as-is from the original.**
- **DO NOT add sections for: languages spoken, hobbies, interests, personal interests, or references.**
- Preserve the structure of any customSections from the original resume
- Improve custom section content the same way as standard sections
- Preserve original date ranges exactly - do not modify years or dates
- Calculate and emphasize total relevant experience duration when it matches requirements
- Do NOT use em dash ("—") anywhere in the writing/output, even if it exists, remove it
- DO NOT add description in Education Section
- Identify and add missing technical skills to the Skills section that are high-priority in the Job Description and are relevant and necessary for the job role.

Job Description:
{job_description}

Keywords to emphasize:
{job_keywords}

Original Resume:
{original_resume}

Output in this JSON format:
{schema}"""

IMPROVE_PROMPT_OPTIONS = [
    {
        "id": "nudge",
        "label": "Light nudge",
        "description": "Minimal edits to better align existing experience.",
    },
    {
        "id": "keywords",
        "label": "Keyword enhance",
        "description": "Blend in relevant keywords without changing role or scope.",
    },
    {
        "id": "full",
        "label": "Full tailor",
        "description": "Comprehensive tailoring using the job description.",
    },
    {
        "id": "Custom",
        "label": "Custom Prompt",
        "description": "Custom prompt defined by the user.",
    }
]

IMPROVE_RESUME_PROMPTS = {
    "nudge": IMPROVE_RESUME_PROMPT_NUDGE,
    "keywords": IMPROVE_RESUME_PROMPT_KEYWORDS,
    "full": IMPROVE_RESUME_PROMPT_FULL,
    "Custom": IMPROVE_RESUME_PROMPT_CUSTOM,
}

DEFAULT_IMPROVE_PROMPT_ID = "keywords"

# Backward-compatible alias
IMPROVE_RESUME_PROMPT = IMPROVE_RESUME_PROMPT_FULL

COVER_LETTER_PROMPT = """Write a brief cover letter for this job application.

IMPORTANT: Write in {output_language}.

Job Description:
{job_description}

Candidate Resume (JSON):
{resume_data}

Requirements:
- 100-150 words maximum
- 3-4 short paragraphs
- Opening: Reference ONE specific thing from the job description (product, tech stack, or problem they're solving) - not generic excitement about "the role"
- Middle: Pick 1-2 qualifications from resume that DIRECTLY match stated requirements - prioritize relevance over impressiveness
- Closing: Simple availability to discuss, no desperate enthusiasm
- If resume shows career transition, frame the pivot as intentional and relevant
- Extract company name from job description - do not use placeholders
- Do NOT invent information not in the resume
- Tone: Confident peer, not eager applicant
- Do NOT use em dash ("—") anywhere in the writing/output, even if it exists, remove it

Output plain text only. No JSON, no markdown formatting."""

OUTREACH_MESSAGE_PROMPT = """Generate a cold outreach message for LinkedIn or email about this job opportunity.

IMPORTANT: Write in {output_language}.

Job Description:
{job_description}

Candidate Resume (JSON):
{resume_data}

Guidelines:
- 70-100 words maximum (shorter than a cover letter)
- First sentence: Reference specific detail from job description (team, product, technical challenge) - never open with "I'm reaching out" or "I saw your posting"
- One sentence on strongest matching qualification with a concrete metric if available
- End with low-friction ask: "Worth a quick chat?" not "I'd love the opportunity to discuss"
- Tone: How you'd message a former colleague, not a stranger
- Do NOT include placeholder brackets
- Do NOT use phrases like "excited about" or "passionate about"
- Do NOT use em dash ("—") anywhere in the writing/output, even if it exists, remove it

Output plain text only. No JSON, no markdown formatting."""

GENERATE_TITLE_PROMPT = """Extract the job title and company name from this job description.

IMPORTANT: Write in {output_language}.

Job Description:
{job_description}

Rules:
- Format: "Role @ Company" (e.g., "Senior Frontend Engineer @ Stripe")
- If the company name is not found, return just the role (e.g., "Senior Frontend Engineer")
- Maximum 60 characters
- Use the most specific role title mentioned
- Do not add any other text, quotes, or formatting

Output the title only, nothing else."""

# Alias for backward compatibility
RESUME_SCHEMA = RESUME_SCHEMA_EXAMPLE
