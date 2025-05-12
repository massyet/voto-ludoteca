from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import os

app = FastAPI()

# Configurazioni percorsi
app.mount("/documents", StaticFiles(directory="documents"), name="documents")
templates = Jinja2Templates(directory="templates")

# 📧 Caricamento email autorizzate
with open("authorized_emails.txt", "r") as f:
    authorized_emails = [line.strip().lower() for line in f.readlines()]

# 📄 Voti caricati da JSON
if os.path.exists("votes.json"):
    with open("votes.json", "r") as f:
        votes = json.load(f)
else:
    votes = {}

########## 📊 Sistema Voti ##########
@app.get("/voto", response_class=HTMLResponse)
async def voto_home(request: Request):
    return templates.TemplateResponse("voto.html", {"request": request, "error": False})

@app.post("/voto/submit", response_class=HTMLResponse)
async def submit_vote(request: Request, email: str = Form(...), voto: str = Form(...)):
    if email.lower() not in authorized_emails:
        return templates.TemplateResponse("voto.html", {"request": request, "error": True})
    
    votes[email.lower()] = voto
    with open("votes.json", "w") as f:
        json.dump(votes, f)
    
    return RedirectResponse(url="/voto/thanks", status_code=303)

@app.get("/voto/thanks", response_class=HTMLResponse)
async def vote_thanks(request: Request):
    return HTMLResponse("<h1>Grazie per aver votato!</h1>")

########## 📁 Repository Documenti ##########
@app.get("/documenti", response_class=HTMLResponse)
async def documenti_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "error": False})

@app.post("/documenti/login", response_class=HTMLResponse)
async def documenti_login(request: Request, email: str = Form(...)):
    if email.lower() in authorized_emails:
        files = os.listdir("documents")
        return templates.TemplateResponse("files.html", {"request": request, "files": files})
    return templates.TemplateResponse("index.html", {"request": request, "error": True})

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join("documents", filename)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=filename)
    return RedirectResponse(url="/documenti")
