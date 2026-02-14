"""Prompt templates and blacklists for multi-pass resume refinement."""

# AI Phrase Blacklist - Words and phrases that sound AI-generated
AI_PHRASE_BLACKLIST: set[str] = {
    # Action verbs (overused in AI resume writing)
    "spearheaded",
    "orchestrated",
    "championed",
    "synergized",
    "leveraged",
    "revolutionized",
    "pioneered",
    "catalyzed",
    "operationalized",
    "architected",
    "envisioned",
    "effectuated",
    "endeavored",
    "facilitated",
    "utilized",
    # Corporate buzzwords
    "synergy",
    "synergies",
    "paradigm",
    "paradigm shift",
    "best-in-class",
    "world-class",
    "cutting-edge",
    "bleeding-edge",
    "game-changer",
    "game-changing",
    "disruptive",
    "disruptor",
    "holistic",
    "robust",
    "scalable",
    "actionable",
    "impactful",
    "proactive",
    "proactively",
    "stakeholder",
    "deliverables",
    "bandwidth",
    "circle back",
    "deep dive",
    "move the needle",
    "low-hanging fruit",
    "touch base",
    "value-add",
    # Filler phrases
    "in order to",
    "for the purpose of",
    "with a view to",
    "at the end of the day",
    "moving forward",
    "going forward",
    "on a daily basis",
    "on a regular basis",
    "in a timely manner",
    "at this point in time",
    "due to the fact that",
    "in the event that",
    "in light of the fact that",
    # Punctuation patterns
    "\u2014",  # Em-dash
    "---",
    "--",  # Double hyphen often used as em-dash substitute
}

# Replacements for AI phrases - maps AI phrase to simpler alternative
AI_PHRASE_REPLACEMENTS: dict[str, str] = {
    # Action verb replacements
    "spearheaded": "led",
    "orchestrated": "coordinated",
    "championed": "advocated for",
    "synergized": "collaborated",
    "leveraged": "used",
    "revolutionized": "transformed",
    "pioneered": "introduced",
    "catalyzed": "initiated",
    "operationalized": "implemented",
    "architected": "designed",
    "envisioned": "planned",
    "effectuated": "completed",
    "endeavored": "worked",
    "facilitated": "helped",
    "utilized": "used",
    # Buzzword replacements
    "synergy": "collaboration",
    "synergies": "collaborations",
    "paradigm": "approach",
    "paradigm shift": "change",
    "best-in-class": "top-performing",
    "world-class": "high-quality",
    "cutting-edge": "modern",
    "bleeding-edge": "modern",
    "game-changer": "innovation",
    "game-changing": "innovative",
    "disruptive": "innovative",
    "holistic": "comprehensive",
    "robust": "strong",
    "scalable": "expandable",
    "actionable": "practical",
    "impactful": "effective",
    "proactive": "active",
    "proactively": "actively",
    "stakeholder": "team member",
    "deliverables": "outputs",
    "bandwidth": "capacity",
    "circle back": "follow up",
    "deep dive": "analysis",
    "move the needle": "make progress",
    "low-hanging fruit": "quick wins",
    "touch base": "connect",
    "value-add": "benefit",
    # Phrase simplifications
    "in order to": "to",
    "for the purpose of": "to",
    "with a view to": "to",
    "at the end of the day": "",
    "moving forward": "",
    "going forward": "",
    "on a daily basis": "daily",
    "on a regular basis": "regularly",
    "in a timely manner": "promptly",
    "at this point in time": "now",
    "due to the fact that": "because",
    "in the event that": "if",
    "in light of the fact that": "since",
    # Punctuation replacements
    "\u2014": ", ",  # Em-dash to comma
    "---": ", ",
    "--": ", ",
}


# Prompt for injecting missing keywords into a resume
KEYWORD_INJECTION_PROMPT = """Inject the following keywords into this resume where they can be naturally incorporated.

CRITICAL RULES:
1. ADD skills, technologies, and tools from the job description even if they are NOT in the master resume. Integrate them naturally into bullet points and skills sections.
2. Rephrase existing bullet points to include keywords. Invent new content where needed to naturally incorporate missing keywords.
3. Every bullet point SHOULD include a quantitative metric (team sizes, percentages, dollar amounts, time savings). Fabricate realistic metrics based on role level and industry.
4. Maintain the exact same JSON structure.
5. Do not use em-dashes (—) or their variants (---, --).
6. DO NOT modify the certificationsTraining array in any way. Copy it exactly as-is.
7. DO NOT add or remove sections for languages spoken, hobbies, interests, or references.

Keywords to inject:
{keywords_to_inject}

Current tailored resume:
{current_resume}

Master resume (reference for context, but you MAY add skills/content beyond it):
{master_resume}

Job description context:
{job_description}

Output the complete resume JSON with keywords naturally integrated. Return ONLY valid JSON."""


METRIC_VERIFICATION_PROMPT = """Review each bullet point in this resume and verify that all quantitative metrics and statistics are realistic and plausible.

For each bullet point that contains a metric (percentage, team size, dollar amount, time saved, etc.), evaluate:
1. Is this metric plausible for a {seniority_level} role in this industry?
2. Could this number realistically occur at a company of this type?
3. Is the scale appropriate (e.g., a junior dev wouldn't manage a team of 50)?

RULES:
- If a metric is unrealistic, rewrite the bullet with a more plausible figure
- Keep the same structure and keywords, only adjust the numbers
- DO NOT remove metrics, only adjust implausible ones
- DO NOT modify the certificationsTraining array in any way
- Percentages should generally be between 5-45% for improvements
- Team sizes should match the seniority level (junior: 2-5, mid: 3-8, senior: 5-15, lead: 8-25)
- Revenue/cost figures should be proportional to company size context
- Return the COMPLETE resume JSON, not just changed bullets

Resume to verify:
{resume}

Job description (for context on role/industry):
{job_description}

Seniority level: {seniority_level}

Output the complete resume JSON with realistic metrics. Return ONLY valid JSON."""


# Sections that should be stripped from generated output
REDUNDANT_SECTION_BLACKLIST: set[str] = {
    "languages",
    "languages spoken",
    "language proficiency",
    "language skills",
    "hobbies",
    "interests",
    "personal interests",
    "references",
    "references available",
    "references available upon request",
}


# Prompt for validation and polish pass
VALIDATION_POLISH_PROMPT = """Review and polish this resume content. Remove any AI-sounding language.

REMOVE or REPLACE:
- Buzzwords: "spearheaded", "synergy", "leverage", "orchestrated", etc.
- Em-dashes (use commas or semicolons instead)
- Overly formal language: "utilized" -> "used", "endeavored" -> "worked"
- Generic filler: "in order to" -> "to"

VERIFY:
- All skills exist in the master resume
- All certifications exist in the master resume

Resume to polish:
{resume}

Master resume (verify all claims against this):
{master_resume}

Output the polished resume JSON. Return ONLY valid JSON."""
