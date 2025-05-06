
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import credentials, auth, initialize_app
from pydantic import BaseModel
from typing import List
from collections import defaultdict

# === Firebase setup ===
cred = credentials.Certificate("serviceAccountKey.json")
initialize_app(cred)

# === Whitelist ===
with open("mail_voto.txt", "r") as f:
    WHITELIST = set(line.strip().lower() for line in f.readlines())

# === In-memory storage ===
user_submissions = {}
game_counter = defaultdict(set)

app = FastAPI()

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

class GameSubmission(BaseModel):
    idToken: str
    titoli: List[str]

@app.post("/submit")
def submit_games(data: GameSubmission):
    print("✅ Richiesta ricevuta")

    try:
        print("🔐 Verifico token...")
        decoded = auth.verify_id_token(data.idToken)
        print("✅ Token valido")
        email = decoded["email"].lower()
    except Exception as e:
        print("❌ Errore nel token:", e)
        raise HTTPException(status_code=401, detail="Token Firebase non valido")

    print("📧 Email:", email)

    if email not in WHITELIST:
        print("⛔ Email non autorizzata")
        raise HTTPException(status_code=403, detail="Email non autorizzata")

    if email in user_submissions:
        print("⚠️ Email ha già votato")
        raise HTTPException(status_code=400, detail="Hai già votato")

    titoli = list(set([t.strip().lower() for t in data.titoli if t.strip()]))

    if len(titoli) == 0:
        print("❌ Nessun titolo valido")
        raise HTTPException(status_code=400, detail="Inserisci almeno un titolo")
    if len(titoli) > 5:
        print("❌ Troppi titoli")
        raise HTTPException(status_code=400, detail="Massimo 5 titoli")

    print("🎲 Titoli ricevuti:", titoli)

    user_submissions[email] = set(titoli)
    for titolo in titoli:
        game_counter[titolo].add(email)

    classifica = get_stats()
    print("📊 Classifica aggiornata:", classifica)
    return classifica

@app.get("/stats")
def get_stats():
    risultati = [
        {"titolo": titolo.title(), "conteggio": len(emails)}
        for titolo, emails in game_counter.items()
    ]
    risultati.sort(key=lambda x: -x["conteggio"])
    return risultati
