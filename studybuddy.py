import os, json, tempfile, time
from datetime import date
from collections import defaultdict
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError, APIStatusError

load_dotenv()
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_BYTES = 20 * 1024 * 1024 
MODEL = "gpt-4o-mini"

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES
CORS(app, resources={r"/api/*": {"origins": "*"}})

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY missing. Put it in .env")
client = OpenAI(api_key=api_key)
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
def clamp_text(s: str, limit_chars: int = 16000) -> str:
    return (s or "").strip()[:limit_chars]
def extract_text_from_upload(file_storage):
    """Return (text, file_name). Supports PDF/DOCX/TXT."""
    filename = file_storage.filename
    ext = filename.rsplit(".", 1)[1].lower()
    raw = file_storage.read()
    if len(raw) > MAX_BYTES:
        raise ValueError("File too large (>20MB)")
    if ext == "txt":
        try:
            return raw.decode("utf-8", errors="ignore"), filename
        except Exception:
            return raw.decode("latin-1", errors="ignore"), filename
    with tempfile.NamedTemporaryFile(delete=True, suffix=f".{ext}") as tmp:
        tmp.write(raw); tmp.flush()
        if ext == "pdf":
            try:
                from pypdf import PdfReader
            except Exception:
                raise RuntimeError("Missing dependency: pypdf")
            reader = PdfReader(tmp.name)
            parts = []
            for page in reader.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n".join(parts), filename
        if ext == "docx":
            try:
                import docx
            except Exception:
                raise RuntimeError("Missing dependency: python-docx")
            d = docx.Document(tmp.name)
            return "\n".join(p.text for p in d.paragraphs), filename

    raise ValueError("Unsupported file type")

def call_openai_for_study_pack(text: str, n_questions: int = 5):
    """
    Return dict: {summary, keyPoints, quizQuestions, studyGuide}
    """
    text = clamp_text(text)
    n = max(1, min(int(n_questions or 5), 20))
    system = (
        "You are StudyBuddy, you will be a friendly study assistant that can break down complex topics into easily understandable pieces. Given course material, "
        f"produce: (1) a tight summary (100-300 words), (2) 5-20 bullet key points, "
        f"(3) {n} MCQs with exactly 4 options each and a correct index (0..3), "
        "(4) a short, actionable study plan (6-8 bullets). Return JSON only."
    )
    user = (
        "Course Material:\n\n" + text +
        "\n\nReturn strict JSON with keys: summary, keyPoints, quizQuestions, studyGuide. "
        "For quizQuestions use: {\"question\":\"...\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"correct\":0}."
    )

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            payload = resp.choices[0].message.content or "{}"
            return json.loads(payload)
        except APIStatusError as e:
            if e.status_code == 429:
                time.sleep(1.2 * (attempt + 1))
                continue
            raise
        except OpenAIError:
            raise
        except Exception:
            return {"summary":"", "keyPoints":[], "quizQuestions":[], "studyGuide":[]}
@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")
@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided (use form field 'file')"}), 400
        f = request.files["file"]
        if f.filename == "":
            return jsonify({"error": "Empty filename"}), 400
        if not allowed_file(f.filename):
            return jsonify({"error": "Unsupported file type (pdf/docx/txt)"}), 400
        n_questions = request.form.get("n", type=int, default=5)
        text, fname = extract_text_from_upload(f)
        if not text.strip():
            return jsonify({"error": "Could not extract text from file"}), 400
        study_pack = call_openai_for_study_pack(text, n_questions)
        study_pack["fileName"] = fname
        return jsonify(study_pack)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
