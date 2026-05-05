from flask import Flask, render_template, request, jsonify
import json
import random
import os
import google.generativeai as genai

app = Flask(__name__)

# Load your 150 questions
with open('questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

# Configure Google Gemini AI
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/question')
def get_question():
    # Pick a random question
    return jsonify(random.choice(questions))

@app.route('/api/coach', methods=['POST'])
def get_coaching():
    # Kept for backward compatibility. No longer called by the UI.
    data = request.json or {}
    instinct = data.get('instinct')
    rationale = data.get('rationale')

    prompt = f"""
    You are an expert NCLEX Nurse Educator.
    The correct rationale for this question is: {rationale}
    The nursing student's 'gut instinct' was: "{instinct}"

    In 2 short, encouraging sentences, tell the student if their instinct was on the right track, and remind them of the core NCLEX safety principle here. Do not give away the exact answer.
    """

    try:
        response = model.generate_content(prompt)
        return jsonify({"note": response.text})
    except Exception:
        return jsonify({"note": "AI Coach is taking a quick break! Trust your gut and look at the options below."})


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
You are an expert NCLEX Nurse Educator coaching a nursing student.

The student just finished a block of {total} questions. Their first-instinct answer was locked in BEFORE seeing the correct answer.

Quick stats:
- {matches} instincts matched the correct answer
- {misses} instincts did not match
- the rest are unclear, such as SATA or bowtie questions

Here are the attempts:

{block_text}

Analyze the student's thinking patterns across this block.

Specifically look for and call out only if you actually see evidence:
- Lack of clinical judgement or missing the obvious priority
- Overthinking or complicating simple questions
- Changing or misordering priorities, such as ignoring ABCs, safety, or Maslow
- Missing safety-first or airway-breathing-circulation cues
- Falling for distractor traps
- Pattern with question type, such as standard vs SATA vs bowtie

Respond in this exact format, plain text, no markdown headers:

Summary: 2-3 sentences naming the main pattern you see.
Strengths: 1-2 short bullets of what the student is doing well.
Watch-outs: 2-4 short bullets of specific thinking traps to fix, each tied to an example from the block by Q number.
Next block focus: 1-2 sentences telling the student what to consciously do differently in the next 20 questions.

Be direct, warm, and specific. Do not list every question. Do not lecture about general NCLEX strategy.
"""

    try:
        response = model.generate_content(prompt)
        return jsonify({"analysis": response.text})
    except Exception:
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
