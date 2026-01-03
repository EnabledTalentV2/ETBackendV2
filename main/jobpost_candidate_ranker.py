# main/jobpost_candidate_ranker.py
# FULLY FIXED & SUPABASE-COMPATIBLE VERSION

from openai import OpenAI
from dotenv import load_dotenv
from django.shortcuts import get_object_or_404
from candidates.models import CandidateProfile
from .models import JobPost, WORKPLACE_TYPES, WORK_TYPES
from pydantic import BaseModel
import json
import datetime
import tiktoken

load_dotenv()
client = OpenAI()


# ------------------------------------------------------------
# Pydantic Skill Expansion Model
# ------------------------------------------------------------
class SkillOutput(BaseModel):
    skills: list[str]


# ------------------------------------------------------------
# Expand skill synonyms using GPT-4o-mini
# ------------------------------------------------------------
def expand_job_skills(job_skills: str):
    prompt = f"""
Generate a list of keyword variations, related technologies, and synonyms 
that would help match resumes for the skill set:

Skills: {job_skills}

Return ONLY a list of skill keywords.
"""

    completion = client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {"role": "developer", "content": "Return JSON strictly matching SkillOutput."},
            {"role": "user", "content": prompt},
        ],
        text_format=SkillOutput
    )

    return [s.lower().strip() for s in completion.output_parsed.skills]


# ------------------------------------------------------------
# Extract skills from resume_data safely
# ------------------------------------------------------------
def extract_resume_skills(resume_json):
    if not resume_json:
        return set()

    # Your parser returns:
    # { "skills": [ {"name": "Python"}, {"name": "SQL"}, ... ] }

    if "skills" in resume_json and isinstance(resume_json["skills"], list):
        names = []
        for item in resume_json["skills"]:
            if isinstance(item, dict) and "name" in item:
                names.append(item["name"])
            elif isinstance(item, str):
                names.append(item)
        return set(s.lower().strip() for s in names)

    return set()


# ------------------------------------------------------------
# Main Ranking Algorithm
# ------------------------------------------------------------
def ranking_algo(job_id: int):
    job = get_object_or_404(JobPost, id=job_id)

    # Map enums → readable text
    workplace = dict(WORKPLACE_TYPES).get(job.workplace_type, "Not specified")
    job_type_text = dict(WORK_TYPES).get(job.job_type, "Not specified")
    job_skills = ", ".join(skill.name for skill in job.skills.all())

    # ------------------------------
    # Skill Expansion
    # ------------------------------
    expanded_skills = expand_job_skills(job_skills)

    # ------------------------------
    # Build Job Description for LLM
    # ------------------------------
    job_description = f"""
JOB OVERVIEW
============
Title: {job.title}
Location: {job.location}
Workplace Mode: {workplace}
Job Type: {job_type_text}
Estimated Salary: {job.estimated_salary}
Visa Required: {"Yes" if job.visa_required else "No"}

Skills Required:
{job_skills}

Job Description:
{job.job_desc}
"""

    # ------------------------------
    # Fetch candidates (Supabase DB via Django ORM)
    # ------------------------------
    candidates_qs = CandidateProfile.objects.filter(
        is_available=True,
        resume_data__isnull=False
    )

    if job.visa_required:
        candidates_qs = candidates_qs.filter(has_workvisa=True)

    # ------------------------------
    # Heuristic Pre-Ranking (cheap filtering)
    # ------------------------------
    scored = []

    for c in candidates_qs:
        resume_json = c.resume_data or {}
        resume_skills = extract_resume_skills(resume_json)
        resume_text_blob = json.dumps(resume_json).lower()

        # Skill match
        overlap = len(set(expanded_skills).intersection(resume_skills))
        if overlap == 0:
            overlap = sum(1 for s in expanded_skills if s in resume_text_blob)

        if overlap == 0:
            continue

        # Preferences match
        work_bonus = (
            1 if workplace.lower() in [str(w).lower() for w in c.work_mode_preferences] 
            else 0
        )

        type_bonus = (
            1 if job_type_text.lower() in [str(t).lower() for t in c.employment_type_preferences]
            else 0
        )

        score = overlap * 3 + work_bonus + type_bonus

        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Limit to top candidates (LLM cost control)
    selected = [c for _, c in scored[:5]]

    # Minimum fallback
    if len(selected) < 3:
        additional = candidates_qs.exclude(id__in=[x.id for x in selected])[:3 - len(selected)]
        selected.extend(additional)

    # ------------------------------
    # Prepare candidates for LLM ranking
    # ------------------------------
    candidates_for_llm = []
    for c in selected:
        candidates_for_llm.append({
            "id": c.id,
            "slug": c.slug,
            "resume_text": json.dumps(c.resume_data, indent=2)
        })

    # ------------------------------
    # Final LLM Ranking
    # ------------------------------
    ranked, token_usage, cost = final_rank_with_llm(job_description, candidates_for_llm)

    result = {
        "ranked_candidates": ranked,
        "token_usage": token_usage,
        "estimated_cost": cost,
        "last_updated": str(datetime.datetime.now())
    }

    job.candidate_ranking_data = result
    job.ranking_status = "ranked"
    job.save()

    return result


# ------------------------------------------------------------
# LLM Ranking Step
# ------------------------------------------------------------
def final_rank_with_llm(job_description, candidates):
    ranked_results = []
    total_input_tokens = total_output_tokens = total_cost = 0

    encoding = tiktoken.get_encoding("cl100k_base")

    system_msg = "You are an AI Talent Matcher."

    for candidate in candidates:

        prompt = f"""
Rate candidate match on a scale of 0–100.

JOB:
{job_description}

CANDIDATE:
{candidate["resume_text"]}

Return JSON:
{{
  "score": number,
  "reasons": ["point1", "point2", "point3"]
}}
"""

        input_tokens = len(encoding.encode(system_msg)) + len(encoding.encode(prompt))
        total_input_tokens += input_tokens

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            output_tokens = len(encoding.encode(content))

            total_output_tokens += output_tokens

            result = json.loads(content)

            ranked_results.append({
                "candidate_id": candidate["id"],
                "candidate_slug": candidate["slug"],
                "score": result["score"],
                "reasons": result["reasons"],
            })

            # Approx cost calculation
            total_cost += (input_tokens / 1000 * 0.01) + (output_tokens / 1000 * 0.03)

        except Exception:
            ranked_results.append({
                "candidate_id": candidate["id"],
                "candidate_slug": candidate["slug"],
                "score": 0,
                "reasons": ["Ranking error"]
            })

    ranked_results.sort(key=lambda x: x["score"], reverse=True)

    return ranked_results, {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens
    }, total_cost
