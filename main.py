from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
GROQ_URL = os.getenv(
    "GROQ_API_URL",
    "https://api.groq.com/openai/v1/chat/completions",
)
MAX_DOCUMENT_CHARS = 80_000
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_SESSION_CHARS = 80_000
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


@dataclass
class StudySession:
    documents: dict[str, str] = field(default_factory=dict)

    @property
    def context(self) -> str:
        return "\n\n".join(
            f"--- {name} ---\n{text}" for name, text in self.documents.items()
        )


session = StudySession()
app = FastAPI(title="Quietly Learn", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class QuestionResponse(BaseModel):
    answer: str
    sources: list[str]


def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return content.decode("utf-8", errors="replace")


async def ask_groq(question: str, context: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured. Add it to your .env file.",
        )

    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    system_prompt = """You are Quietly Learn, a patient study companion.
Answer using the provided study notes whenever possible. If the notes do not contain
the answer, say so clearly instead of inventing facts, then give a short helpful
general explanation only if it is safe and useful. Prefer clear language, small
sections, and examples. Never overwhelm the student. For quiz requests, ask one
question at a time unless the student requests a list."""
    user_prompt = f"Study notes:\n{context or '(No notes uploaded yet)'}\n\nStudent question:\n{question}"

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": 0.3,
                    "max_tokens": 900,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = "Groq could not answer right now."
        try:
            detail = exc.response.json().get("error", {}).get("message", detail)
        except ValueError:
            pass
        raise HTTPException(status_code=502, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not reach Groq.") from exc

    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=502, detail="Groq returned an unexpected response.") from exc


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/session")
async def get_session() -> dict[str, object]:
    return {
        "documents": [
            {"name": name, "characters": len(text)}
            for name, text in session.documents.items()
        ],
        "ready": bool(session.documents),
    }


@app.post("/api/documents")
async def upload_documents(
    files: Annotated[list[UploadFile], File(description="Study documents")]
) -> dict[str, object]:
    if not files:
        raise HTTPException(status_code=400, detail="Choose at least one document.")

    pending_documents: dict[str, str] = {}
    for file in files:
        filename = file.filename or "untitled"
        if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail=f"{filename}: use TXT, MD, or PDF files.")
        content = await file.read(MAX_FILE_BYTES + 1)
        await file.close()
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{filename} is too large. Keep each study file under 2 MB.",
            )
        try:
            text = extract_text(filename, content).strip()
        except (PdfReadError, OSError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"{filename} could not be read. Try a text-based PDF or TXT/MD file.",
            ) from exc
        if not text:
            raise HTTPException(status_code=422, detail=f"{filename} does not contain readable text.")
        pending_documents[filename] = text[:MAX_DOCUMENT_CHARS]

    session.documents.update(pending_documents)
    all_documents = [
        {"name": name, "characters": len(text)}
        for name, text in session.documents.items()
    ]
    return {"documents": all_documents, "ready": True}


@app.delete("/api/documents")
async def clear_documents() -> dict[str, bool]:
    session.documents.clear()
    return {"ready": False}


@app.post("/api/questions", response_model=QuestionResponse)
async def answer_question(request: QuestionRequest) -> QuestionResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Ask a question before submitting.")
    answer = await ask_groq(question, session.context[:MAX_SESSION_CHARS])
    return QuestionResponse(answer=answer, sources=list(session.documents))
