import boto3
import json
import os
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

MODEL = "eu.anthropic.claude-sonnet-4-6"

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    config=Config(
        read_timeout=300,
        connect_timeout=10,
        retries={"max_attempts": 2, "mode": "standard"},
    ),
)

SYSTEM_PROMPT = (
    "You are a senior data engineering mentor. You help a mid-level data engineer "
    "prepare for a senior-level assessment. Be practical, give real-world examples, "
    "and always explain at the depth expected of a senior engineer. "
    "Use clear structure with headers and bullet points."
)


def _ask(user_prompt: str, system: str = SYSTEM_PROMPT, max_tokens: int = 4096) -> str:
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
    })
    response = bedrock.invoke_model(
        modelId=MODEL,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def explain_subtopic(subtopic_name: str, description: str, senior_level: str) -> str:
    return _ask(
        f"Explain the following data engineering subtopic at the senior level ({senior_level}).\n\n"
        f"**Subtopic:** {subtopic_name}\n"
        f"**Description:** {description}\n\n"
        f"Cover:\n"
        f"1. Core concepts a senior DE must know\n"
        f"2. Common pitfalls and best practices\n"
        f"3. Real-world use cases and examples\n"
        f"4. How this connects to other data engineering topics\n\n"
        f"At the end, provide a concise summary (3-5 bullet points)."
    )


def suggest_resources(subtopic_name: str) -> str:
    return _ask(
        f"Suggest curated learning resources for a mid-level data engineer studying "
        f"'{subtopic_name}' to reach senior level. Include:\n"
        f"- 2-3 video resources (YouTube, courses)\n"
        f"- 2-3 documentation/article links\n"
        f"- 1-2 hands-on tutorials or labs\n\n"
        f"For each resource, briefly explain why it's valuable.",
        max_tokens=2048,
    )


def generate_task(subtopic_name: str, description: str, difficulty: int, weak_areas: str = None) -> str:
    weak_ctx = ""
    if weak_areas:
        weak_ctx = f"\nThe learner has these weak areas to focus on: {weak_areas}\n"

    return _ask(
        f"Generate a practice task for a data engineer studying '{subtopic_name}'.\n"
        f"Description: {description}\n"
        f"Difficulty: {difficulty}/5 (1=basic, 5=expert)\n"
        f"{weak_ctx}\n"
        f"Choose ONE of these formats:\n"
        f"- **Hands-on task**: A practical coding/configuration exercise\n"
        f"- **Quiz question**: A multiple-choice or short-answer question\n"
        f"- **Real-world scenario**: A situation requiring analysis and a solution\n\n"
        f"Clearly state the format, the task/question, and what a correct answer should cover. "
        f"Do NOT reveal the answer.",
        max_tokens=2048,
    )


def evaluate_answer(task_description: str, user_answer: str, subtopic_name: str) -> dict:
    response_text = _ask(
        f"Evaluate this answer for a senior-level data engineering assessment.\n\n"
        f"**Subtopic:** {subtopic_name}\n"
        f"**Task:** {task_description}\n"
        f"**Answer:** {user_answer}\n\n"
        f"Respond in this exact format:\n"
        f"VERDICT: CORRECT or INCORRECT\n\n"
        f"FEEDBACK:\n"
        f"(Detailed explanation of what's right, what's wrong, what's missing)\n\n"
        f"WEAK_AREAS:\n"
        f"(Comma-separated list of specific weak areas identified, or 'none')\n\n"
        f"HINT:\n"
        f"(If incorrect, give a specific hint to improve. If correct, suggest next challenge.)",
        max_tokens=2048,
    )

    lines = response_text.strip().split("\n")
    verdict = "INCORRECT"
    feedback = ""
    weak_areas = ""
    hint = ""
    current_section = ""

    for line in lines:
        if line.startswith("VERDICT:"):
            verdict = "CORRECT" if "CORRECT" in line.upper().split("VERDICT:")[1] and "INCORRECT" not in line.upper().split("VERDICT:")[1] else "INCORRECT"
        elif line.startswith("FEEDBACK:"):
            current_section = "feedback"
        elif line.startswith("WEAK_AREAS:"):
            current_section = "weak_areas"
        elif line.startswith("HINT:"):
            current_section = "hint"
        else:
            if current_section == "feedback":
                feedback += line + "\n"
            elif current_section == "weak_areas":
                weak_areas += line + "\n"
            elif current_section == "hint":
                hint += line + "\n"

    return {
        "correct": verdict == "CORRECT",
        "feedback": feedback.strip(),
        "weak_areas": weak_areas.strip(),
        "hint": hint.strip(),
        "raw": response_text,
    }


def generate_eval_questions(subtopic_name: str, description: str, senior_level: str) -> str:
    """Returns raw JSON string of questions for parsing."""
    # Number of questions by required depth
    counts = {"L2": (3, 2), "L3": (5, 3), "L4": (6, 4)}
    mc_count, text_count = counts.get(senior_level, (5, 3))

    return _ask(
        f"Generate a senior-level assessment test for a data engineer on this subtopic.\n\n"
        f"Subtopic: {subtopic_name}\n"
        f"Description: {description}\n"
        f"Required level: {senior_level}\n\n"
        f"Create exactly {mc_count} multiple-choice questions and {text_count} text-answer questions.\n\n"
        f"Return ONLY a valid JSON array. No explanation before or after. Format:\n"
        f'[\n'
        f'  {{\n'
        f'    "question": "question text",\n'
        f'    "type": "multiple_choice",\n'
        f'    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},\n'
        f'    "correct": "B",\n'
        f'    "explanation": "why B is correct"\n'
        f'  }},\n'
        f'  {{\n'
        f'    "question": "question text",\n'
        f'    "type": "text",\n'
        f'    "model_answer": "reference answer a senior engineer would give",\n'
        f'    "explanation": "key points that must be covered"\n'
        f'  }}\n'
        f']\n\n'
        f"Requirements:\n"
        f"- Multiple-choice options must be plausible (no obvious wrong answers)\n"
        f"- Text questions should require explanation or design thinking, not one-word answers\n"
        f"- Questions must test {senior_level}-level depth — not trivial definitions\n"
        f"- Vary question difficulty: some straightforward, some edge-case/scenario-based\n"
        f"- Keep each model_answer concise (3-5 sentences max) to stay within token limits",
        max_tokens=8192,
    )


def evaluate_text_answers(questions_and_answers: list, subtopic_name: str) -> str:
    """
    questions_and_answers: list of dicts with keys: question, model_answer, explanation, user_answer
    Returns raw JSON string with evaluations.
    """
    qa_block = ""
    for i, qa in enumerate(questions_and_answers, 1):
        qa_block += (
            f"\n--- Question {i} ---\n"
            f"Question: {qa['question']}\n"
            f"Model answer: {qa['model_answer']}\n"
            f"Key points: {qa['explanation']}\n"
            f"User's answer: {qa['user_answer']}\n"
        )

    return _ask(
        f"Evaluate these text answers for a senior data engineering assessment on '{subtopic_name}'.\n"
        f"{qa_block}\n\n"
        f"Return ONLY a valid JSON array (one object per question, same order). No text before or after:\n"
        f'[\n'
        f'  {{\n'
        f'    "correct": true,\n'
        f'    "verdict": "Correct" | "Partially Correct" | "Incorrect",\n'
        f'    "feedback": "specific, concise feedback on what was right/wrong/missing",\n'
        f'    "weak_areas": "comma-separated weak areas, or empty string if none"\n'
        f'  }}\n'
        f']\n\n'
        f"Be strict — senior level means completeness and precision matter.",
        max_tokens=3000,
    )


def deep_evaluate(solution: str, subtopic_name: str, description: str) -> str:
    return _ask(
        f"Provide a detailed senior-level evaluation of this solution/explanation.\n\n"
        f"**Subtopic:** {subtopic_name}\n"
        f"**Description:** {description}\n"
        f"**Submitted work:**\n{solution}\n\n"
        f"Structure your feedback as:\n"
        f"## What's Right\n(strengths)\n\n"
        f"## What's Wrong\n(errors or misconceptions)\n\n"
        f"## What's Missing for Senior Level\n(gaps to fill)\n\n"
        f"## Weak Spots Identified\n(specific areas to improve — list as comma-separated)\n\n"
        f"## Recommended Next Steps\n(concrete actions)",
        max_tokens=3000,
    )
