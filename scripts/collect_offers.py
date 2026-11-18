#!/usr/bin/env python3
"""Collecte d'offres via l'API Adzuna, sans publier les identifiants."""
import datetime as dt
import html
import json
import os
import pathlib
import re
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "offres.json"
QUERIES = [
    "designer produit", "concepteur agenceur", "dessinateur agencement",
    "concepteur vendeur cuisine", "dessinateur mobilier", "dessinateur CAO",
    "bureau études mobilier", "designer packaging", "prototypiste",
]
KEYWORDS = {
    "agencement": 22, "agenceur": 22, "cuisine": 18, "mobilier": 22,
    "dessinateur": 15, "cao": 15, "conception": 12, "designer": 18,
    "produit": 14, "packaging": 18, "prototype": 18, "3d": 10,
    "bureau d'études": 16, "junior": 8, "nantes": 6,
}
def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", str(s or ""))).strip()

def score(job):
    text = (job["title"] + " " + job["description"]).lower()
    return min(100, 30 + sum(v for k, v in KEYWORDS.items() if k in text))

def contract(text):
    t = text.lower()
    if "intérim" in t or "interim" in t or "temporary" in t: return "Intérim"
    if "cdd" in t or "fixed term" in t: return "CDD"
    if "cdi" in t or "permanent" in t: return "CDI"
    return "À vérifier"

def main():
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        print("ADZUNA_APP_ID et ADZUNA_APP_KEY manquants : aucun appel API.")
        return
    jobs = {}
    errors = []
    for query in QUERIES:
        params = urllib.parse.urlencode({
            "app_id": app_id, "app_key": app_key, "what": query,
            "where": "Nantes", "distance": 35,
            "results_per_page": 30, "sort_by": "date",
        })
        url = "https://api.adzuna.com/v1/api/jobs/fr/search/1?" + params
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "RadarEmploiNantes/1.0"})
            with urllib.request.urlopen(request, timeout=25) as response:
                results = json.load(response).get("results", [])
            for item in results:
                ident = str(item.get("id") or item.get("redirect_url"))
                title = clean(item.get("title"))
                desc = clean(item.get("description"))
                if not title or not ident: continue
                job = {
                    "id": ident, "title": title,
                    "company": clean((item.get("company") or {}).get("display_name")),
                    "location": clean((item.get("location") or {}).get("display_name")),
                    "contract": contract(title + " " + desc),
                    "description": desc,
                    "created": item.get("created") or "",
                    "url": item.get("redirect_url") or "",
                    "source": "Adzuna", "score": 0,
                }
                job["score"] = score(job)
                jobs[ident] = job
        except Exception as e:
            errors.append(query + ": " + type(e).__name__)
    if errors and not jobs:
        raise RuntimeError("Échec de la collecte : " + "; ".join(errors))
    result = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "partial" if errors else "ok",
        "message": "Certaines recherches ont échoué." if errors else "",
        "offers": sorted(jobs.values(), key=lambda j: (j["score"], j["created"]), reverse=True),
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(jobs)} annonces collectées ; {len(errors)} requêtes en échec")

if __name__ == "__main__":
    main()
