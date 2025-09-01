import os
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from openai import OpenAI
from dotenv import load_dotenv

# Load environment vars
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey123")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


@app.route("/")
def index():
    """Landing page for interview setup."""
    return render_template("index.html")


@app.route("/submit_role", methods=["POST"])
def submit_role():
    """
    Saves job details from the form into session and redirects to /interview.
    """
    session["interview_role"] = request.form.get("interview_role")
    session["candidate_years_of_experience"] = request.form.get(
        "candidate_years_of_experience")
    session["job_important_skills"] = request.form.get("job_important_skills")
    session["job_level"] = request.form.get("job_level")

    return redirect(url_for("interview"))


@app.route("/interview")
def interview():
    """Interview page with voice + text UI."""
    return render_template("interview.html")


@app.route("/session")
def create_realtime_session():
    """
    Creates an ephemeral Realtime session with OpenAI.
    The browser will call this to get a short-lived token.
    """
    # Build a system prompt using values saved in session
    role = session.get("interview_role", "Software Engineer")
    years = session.get("candidate_years_of_experience", "0")
    skills = session.get("job_important_skills", "")
    level = session.get("job_level", "Junior")

    system_prompt = (
        f"You are an AI interviewer for a {role} position. "
        f"Interview a {level} candidate with {years} years of experience. "
        f"Focus on skills: {skills}. "
        "Ask one question at a time, adjusting difficulty based on their answers."
    )

    r = requests.post(
        "https://api.openai.com/v1/realtime/sessions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-realtime",
            "voice": "shimmer",
            "modalities": ["audio", "text"],
            "instructions": system_prompt,  # inject job details into prompt
        },
        timeout=10,
    )
    r.raise_for_status()
    return jsonify(r.json())


if __name__ == "__main__":
    app.run(debug=True)
