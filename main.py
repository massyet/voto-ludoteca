import os
import json
import threading
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from firebase_admin import credentials, auth, initialize_app
from pydantic import BaseModel
from typing import List
from collections import defaultdict
from difflib import get_close_matches

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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

class GameSubmission(BaseModel):
    idToken: str
    titoli: List[str]

class ResetRequest(BaseModel):
    password: str

RESET_PASSWORD = "resettaggio666"
VOTI_FILE = "voti.json"
voti_lock = threading.Lock()

# === Carica voti all'avvio ===
def carica_voti():
    try:
        with open(VOTI_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {email: set(titoli) for email, titoli in data.items()}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Errore caricamento voti: {e}")
        return {}

def salva_voti():
    with voti_lock:
        with open(VOTI_FILE, "w", encoding="utf-8") as f:
            json.dump({email: list(titoli) for email, titoli in voti.items()}, f, ensure_ascii=False, indent=2)

voti = carica_voti()

def verifica_titolo_bgg(titolo):
    url = "https://boardgamegeek.com/xmlapi2/search"
    params = {"query": titolo, "type": "boardgame"}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code != 200:
            raise HTTPException(status_code=503, detail="Servizio BoardGameGeek non disponibile.")

        if titolo.lower() in response.text.lower():
            return True, None  # Titolo trovato

        # 🔥 Prova a suggerire il primo risultato trovato
        start = response.text.find('name value="')
        if start != -1:
            start += len('name value="')
            end = response.text.find('"', start)
            suggestion = response.text[start:end]
            return False, suggestion  # Titolo non trovato, ma suggerimento disponibile

        return False, None  # Nessun suggerimento trovato

    except requests.RequestException as e:
        print(f"Errore nella richiesta a BoardGameGeek: {e}")
        raise HTTPException(status_code=503, detail="Errore di rete durante la verifica del titolo.")

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

    titoli_non_valdi = []
    for titolo in data.titoli:
        if not verifica_titolo_bgg(titolo):
            titoli_non_valdi.append(titolo)

    if titoli_non_valdi:
        raise HTTPException(status_code=400, detail=f"I seguenti titoli non sono validi: {', '.join(titoli_non_valdi)}")

    with voti_lock:
        voti[email] = set(data.titoli)
        salva_voti()

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

@app.post("/reset")
def reset_voti(data: ResetRequest):
    if data.password != RESET_PASSWORD:
        raise HTTPException(status_code=403, detail="Password non corretta.")
    with voti_lock:
        voti.clear()
        salva_voti()
    return {"status": "ok", "message": "Voti resettati con successo"}
