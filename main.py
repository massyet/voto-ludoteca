import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from firebase_admin import credentials, auth, initialize_app
from pydantic import BaseModel
from typing import List
from collections import defaultdict

# === Firebase ===
raw_key = os.getenv("FIREBASE_KEY")
if not raw_key:
    raise RuntimeError("Variabile FIREBASE_KEY non trovata")
key_json = json.loads(raw_key.encode().decode("unicode_escape"))
cred = credentials.Certificate(key_json)
initialize_app(cred)

# === Whitelist ===
try:
    with open("mail_voto.txt", "r") as f:
        WHITELIST = set(line.strip().lower() for line in f if line.strip())
except FileNotFoundError:
    WHITELIST = set()
    print("⚠️ mail_voto.txt non trovato. Nessun utente sarà autorizzato.")

# === FastAPI app ===
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve i file statici sotto /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Gestisce la root per caricare index.html
@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

# === Modello dati ===
class GameSubmission(BaseModel):
    idToken: str
    titoli: List[str]

voti = defaultdict(set)

@app.post("/submit")
def submit_games(data: GameSubmission):
    try:
        decoded = auth.verify_id_token(data.idToken)
        email = decoded.get("email", "").lower()
    except Exception:
        raise HTTPException(status_code=401, detail="Token Firebase non valido")

    if email not in WHITELIST:
        raise HTTPException(status_code=403, detail="Email non autorizzata")

    if not (1 <= len(data.titoli) <= 5):
        raise HTTPException(status_code=400, detail="Inserisci da 1 a 5 titoli.")

    voti[email] = set(data.titoli)
    return get_classifica()

@app.get("/stats")
def get_classifica():
    conteggio = defaultdict(int)
    for giochi in voti.values():
        for gioco in giochi:
            conteggio[gioco] += 1
    return sorted(
        [{"titolo": titolo.title(), "conteggio": count} for titolo, count in conteggio.items()],
        key=lambda x: x["conteggio"],
        reverse=True
    )