import os
import time
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from typing import Optional
from fastapi.responses import Response, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Load environment vars
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = FastAPI(title="AI Interviewer Service")

# Mount static + templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Metrics
REQUEST_COUNT = Counter("requests_total", "Total number of requests", [
                        "endpoint", "method"])
REQUEST_LATENCY = Histogram(
    "request_latency_seconds", "Request latency", ["endpoint", "method"])
ERROR_COUNT = Counter("errors_total", "Total number of errors", [
                      "endpoint", "method"])

# In-memory session store (simple, not for production scale)
SESSION = {}


@app.middleware("http")
async def add_metrics(request: Request, call_next):
    start_time = time.time()
    endpoint = request.url.path
    method = request.method

    try:
        response = await call_next(request)
        latency = time.time() - start_time
        REQUEST_COUNT.labels(endpoint=endpoint, method=method).inc()
        REQUEST_LATENCY.labels(
            endpoint=endpoint, method=method).observe(latency)
        return response
    except Exception:
        ERROR_COUNT.labels(endpoint=endpoint, method=method).inc()
        raise


@app.get("/healthz")
async def healthz():
    """Readiness probe."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page for interview setup."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/submit_role")
async def submit_role(
    request: Request,
    interview_role: str = Form(...),
    candidate_years_of_experience: str = Form(...),
    job_important_skills: Optional[str] = Form(None),
    job_level: str = Form(...),
):
    """Saves job details into memory and redirects to /interview."""
    SESSION["interview_role"] = interview_role
    SESSION["candidate_years_of_experience"] = candidate_years_of_experience
    SESSION["job_important_skills"] = job_important_skills
    SESSION["job_level"] = job_level
    return RedirectResponse(url="/interview", status_code=303)


@app.get("/interview", response_class=HTMLResponse)
async def interview(request: Request):
    """Interview page with voice + text UI."""
    return templates.TemplateResponse("interview.html", {"request": request})


@app.get("/session")
async def create_realtime_session():
    """
    Creates an ephemeral Realtime session with OpenAI.
    Injects job details into the system prompt.
    """
    role = SESSION.get("interview_role", "Software Engineer")
    years = SESSION.get("candidate_years_of_experience", "0")
    skills = SESSION.get("job_important_skills", "")
    level = SESSION.get("job_level", "Junior")

    system_prompt = (
        f"You are an AI interviewer for a {role} position. "
        f"Interview a {level} candidate with {years} years of experience. "
        f"Focus on skills: {skills}. "
        "Ask one question at a time, adjusting difficulty based on their answers."
    )

    try:
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
                "instructions": system_prompt,
            },
            timeout=10,
        )
        r.raise_for_status()
        return JSONResponse(r.json())
    except requests.RequestException as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
