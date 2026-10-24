# Quietly Learn

A calm, focused learning agent powered by FastAPI and Groq.

This is intentionally a low-effort MVP for learning and experimentation, not a
production education platform. It keeps one study session in server memory and
does not include accounts, a database, document search, or persistent storage.

## Features

- Upload `.txt`, `.md`, and `.pdf` study notes.
- Keep each uploaded file under 2 MB for predictable processing.
- Ask questions grounded in the uploaded material.
- Use suggested prompts for summaries, revision, and quizzes.
- Streamlined single-page interface with no account or database required for the MVP.

## Run locally

1. Create a virtual environment and install dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and add a Groq API key.

3. Start the app:

   ```powershell
   uvicorn app.main:app --reload
   ```

4. Open <http://127.0.0.1:8000>.

## Model and file-size note

The default model is `openai/gpt-oss-20b`. Groq documents it as a 20B-total-parameter
Mixture-of-Experts model with a 131,072-token context window and a 65,536-token
maximum output. Those are model limits, not a promise that very large files will
produce good answers. This MVP deliberately accepts files up to 2 MB and sends a
small bounded text context so the free API remains responsive and answers stay
focused. Scanned/image-only PDFs may not contain extractable text.

Model reference: [Groq GPT-OSS 20B documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b).

## Architecture

The browser sends files and questions to the FastAPI backend. The backend extracts text, keeps the current study session in memory, and sends a carefully constrained prompt to Groq. This keeps the API key off the client and makes the provider easy to replace later.

For production, replace the in-memory `StudySession` with a database/object store, add authentication and rate limiting, and chunk/index large documents with embeddings or a vector store.
