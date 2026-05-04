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
    data = request.json
    instinct = data.get('instinct')
    rationale = data.get('rationale')
    
    # The prompt that tells Gemini how to act
    prompt = f"""
    You are an expert NCLEX Nurse Educator. 
    The correct rationale for this question is: {rationale}
    The nursing student's 'gut instinct' was: "{instinct}"
    
    In 2 short, encouraging sentences, tell the student if their instinct was on the right track, and remind them of the core NCLEX safety principle here. Do not give away the exact answer.
    """
    
    try:
        response = model.generate_content(prompt)
        return jsonify({"note": response.text})
    except Exception as e:
        # Fallback if the API times out
        return jsonify({"note": "AI Coach is taking a quick break! Trust your gut and look at the options below."})

if __name__ == '__main__':
    app.run(debug=True)