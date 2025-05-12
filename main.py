from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import json
import os
import requests

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 📧 Caricamento email autorizzate
with open("authorized_emails.txt", "r") as f:
    authorized_emails = [line.strip().lower() for line in f.readlines()]

# 📄 Caricamento voti
votes_file = "votes.json"
if os.path.exists(votes_file):
    with open(votes_file, "r") as f:
        votes = json.load(f)
else:
    votes = {}

def search_bgg_game(title):
    """Verifica il titolo su BoardGameGeek e suggerisce il più simile."""
    url = "https://boardgamegeek.com/xmlapi2/search"
    params = {"query": title, "type": "boardgame"}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None
    if "<item " not in response.text:
        return None
    start = response.text.find('name value="') + len('name value="')
    end = response.text.find('"', start)
    suggestion = response.text[start:end]
    return suggestion

@app.get("/", response_class=HTMLResponse)
async def voto_home(request: Request):
    return templates.TemplateResponse("voto.html", {"request": request, "error": False, "suggestion": None})

@app.post("/voto", response_class=HTMLResponse)
async def submit_vote(request: Request, email: str = Form(...), title: str = Form(...)):
    email = email.lower()
    title = title.strip()

    if email not in authorized_emails:
        return templates.TemplateResponse("voto.html", {"request": request, "error": True, "suggestion": None})

    if email in votes:
        return HTMLResponse("<h1>Hai già votato. Grazie!</h1>")

    suggestion = search_bgg_game(title)
    if suggestion and suggestion.lower() != title.lower():
        return templates.TemplateResponse("voto.html", {
            "request": request,
            "error": True,
            "suggestion": suggestion
        })

    votes[email] = title
    with open(votes_file, "w") as f:
        json.dump(votes, f)

    return RedirectResponse(url="/grazie", status_code=303)

@app.get("/grazie", response_class=HTMLResponse)
async def grazie(request: Request):
    return HTMLResponse("<h1>Grazie per aver votato!</h1>")

@app.get("/classifica", response_class=HTMLResponse)
async def classifica(request: Request):
    counter = {}
    for game in votes.values():
        counter[game] = counter.get(game, 0) + 1
    sorted_votes = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    result = "<h1>📊 Classifica Giochi</h1><ul>"
    for game, count in sorted_votes:
        result += f"<li>{game}: {count} voti</li>"
    result += "</ul>"
    return HTMLResponse(result)
