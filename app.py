from flask import Flask, render_template, request, jsonify
import json
import random
import os
import urllib.request
import urllib.error

app = Flask(__name__)

# Load your questions
with open('questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)


def ask_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise Exception("GEMINI_API_KEY is missing in Render environment variables.")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent?key="
        + api_key
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["candidates"][0]["content"]["parts"][0]["text"]


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/question')
def get_question():
    return jsonify(random.choice(questions))


@app.route('/api/coach', methods=['POST'])
def get_coaching():
    # Kept for backward compatibility. The main UI no longer uses this after every question.
    data = request.json or {}
    instinct = data.get('instinct')
    rationale = data.get('rationale')

    prompt = f"""
You are an expert NCLEX Nurse Educator.

The correct rationale for this question is:
{rationale}

The nursing student's first instinct was:
{instinct}

In 2 short, encouraging sentences, tell the student if their instinct was on the right track and remind them of the core NCLEX safety principle here. Do not give away the exact answer.
"""

    try:
        note = ask_gemini(prompt)
        return jsonify({"note": note})
    except Exception as e:
        print("Gemini /api/coach error:", str(e))
        return jsonify({
            "note": "AI Coach is taking a quick break! Trust your gut and look at the options below."
        })


def _format_attempts_for_prompt(attempts):
    lines = []

    for i, a in enumerate(attempts, start=1):
        stem = (a.get('stem') or '').strip().replace('\n', ' ')
        if len(stem) > 400:
            stem = stem[:400] + '...'

        qtype = a.get('type') or 'standard'
        instinct = (a.get('instinct') or '').strip()
        correct = a.get('correct')

        if isinstance(correct, (dict, list)):
            correct_str = json.dumps(correct)
        else:
            correct_str = str(correct) if correct is not None else ''

        matched = a.get('matched')
        if matched is True:
            match_str = 'MATCH'
        elif matched is False:
            match_str = 'MISS'
        else:
            match_str = 'unclear'

        rationale = (a.get('rationale') or '').strip().replace('\n', ' ')
        if len(rationale) > 300:
            rationale = rationale[:300] + '...'

        trap = (a.get('trap') or '').strip().replace('\n', ' ')
        if len(trap) > 300:
            trap = trap[:300] + '...'

        lines.append(
            f"Q{i} [{qtype}] match={match_str}\n"
            f"  Stem: {stem}\n"
            f"  Student first instinct: {instinct}\n"
            f"  Correct: {correct_str}\n"
            f"  Rationale: {rationale}\n"
            f"  Trap: {trap}"
        )

    return "\n\n".join(lines)


@app.route('/api/analyze-block', methods=['POST'])
def analyze_block():
    data = request.json or {}
    attempts = data.get('attempts') or []

    if not attempts:
        return jsonify({"analysis": "No attempts were provided to analyze."})

    block_text = _format_attempts_for_prompt(attempts)

    total = len(attempts)
    misses = sum(1 for a in attempts if a.get('matched') is False)
    matches = sum(1 for a in attempts if a.get('matched') is True)

    prompt = f"""
You are an expert NCLEX RN educator coaching a nursing student.

The student just completed a block of {total} NCLEX questions.
Their first-instinct answer was locked BEFORE seeing the correct answer.

Quick stats:
- {matches} instincts matched the correct answer
- {misses} instincts did not match
- the rest are unclear, such as SATA or bowtie questions

Here are the attempts:

{block_text}

Analyze the student's thinking patterns across this block.

Specifically look for evidence of:
- lack of clinical judgment
- overthinking
- complicating simple questions
- missing the obvious priority
- ignoring ABCs, safety, Maslow, acute vs chronic, or stable vs unstable
- falling for distractor traps
- weakness by question type, such as standard, SATA, or bowtie

Respond in this exact format:

Summary: 2-3 sentences naming the main thinking pattern.

Strengths:
- 1-2 short bullets.

Watch-outs:
- 2-4 short bullets, each tied to an example from the block by Q number.

Next block focus: 1-2 sentences telling the student what to consciously do differently in the next 20 questions.

Be direct, warm, specific, and practical. Do not list every question. Do not give a generic NCLEX lecture.
"""

    try:
        analysis = ask_gemini(prompt)
        return jsonify({"analysis": analysis})
    except Exception as e:
        print("Gemini /api/analyze-block error:", str(e))
        return jsonify({
            "analysis": (
                "AI Coach is taking a quick break, so here is a self-check instead:\n"
                "Summary: You finished another block of " + str(total) + " questions. Nice consistency.\n"
                "Watch-outs: Re-read any question you missed and ask yourself: did I pick the SAFEST action, or just a reasonable one? Did I follow ABCs and Maslow?\n"
                "Next block focus: Before locking your instinct, name the priority framework the question is testing: ABC, safety, Maslow, acute vs chronic, or stable vs unstable."
            )
        })


if __name__ == '__main__':
    app.run(debug=True)
