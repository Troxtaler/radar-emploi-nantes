#!/usr/bin/env python3
"""Radar Emploi Nantes: collecteur multi-source, sources publiques autorisées.

Connecteurs: Greenhouse Job Board API, Lever Postings API, flux RSS/Atom
explicitement configurés. Adzuna reste une source optionnelle.
Ne contourne aucune authentification, limitation d'accès ou protection anti-bot.
"""
import datetime as dt
import html
import json
import os
import pathlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[1]
CONFIG=ROOT/"sources.json"
DEST=ROOT/"data"/"offres.json"
AGENT="RadarEmploiNantes/2.0 (public jobs feeds)"
KEYWORDS={"agencement":23,"agenceur":23,"cuisine":19,"mobilier":22,"dessinateur":17,"cao":17,"conception":12,"designer":18,"produit":14,"packaging":17,"prototype":18,"3d":10,"bureau d'études":16,"junior":9}
TERMS=("designer produit","concepteur agenceur","dessinateur agencement","concepteur vendeur cuisine","dessinateur mobilier","dessinateur cao","bureau d'études","designer packaging","prototypiste","plv","mobilier sur mesure")
NEAR=("nantes","saint-herblain","rezé","orvault","carquefou","vertou","bouguenais","basse-goulaine","haute-goulaine","sainte-luce-sur-loire","saint-sébastien-sur-loire","la chapelle-sur-erdre","couëron","sautron","treillières","grandchamp-des-fontaines","saint-aignan-grandlieu","les sorinières","bouaye","saint-philbert-de-grand-lieu","vigneux-de-bretagne","pornic","clisson","ancenis","machecoul","vallet","savenay")
def strip(s):return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",str(s or "")))).strip()
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":AGENT,"Accept":"application/json, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req,timeout=22) as resp:return resp.read()
def kind(text):
    t=text.lower()
    if "intérim" in t or "interim" in t:return "Intérim"
    if "cdd" in t or "fixed-term" in t:return "CDD"
    if "cdi" in t or "permanent" in t:return "CDI"
    return "À vérifier"
def relevance(title,desc):
    text=(title+" "+desc).lower()
    return min(100,20+sum(v for k,v in KEYWORDS.items() if k in text))
def relevant(job):
    text=(job["title"]+" "+job["description"]).lower()
    loc=job["location"].lower()
    return any(x in text for x in ("design","agenc","mobilier","cuisine","dessin","cao","packaging","prototype","plv","bureau d'études","conception","ébénist","menuiser")) and (not loc or any(x in loc for x in NEAR))
def add(out,*,source,identifier,title,company,location,description,url,created="",contract=""):
    if not str(url).startswith(("https://","http://")):return
    job={"id":str(source)+":"+str(identifier or url),"source":source,"title":strip(title),"company":strip(company),"location":strip(location),"description":strip(description),"url":str(url),"created":str(created or ""),"contract":contract or kind(str(title)+" "+str(description))}
    job["score"]=relevance(job["title"],job["description"])
    if job["title"] and relevant(job):out[job["id"]]=job
def greenhouse(item,out):
    token=item["board_token"]
    url="https://boards-api.greenhouse.io/v1/boards/"+urllib.parse.quote(token,safe="")+"/jobs?content=true"
    for j in json.loads(fetch(url)).get("jobs",[]):
        add(out,source="Greenhouse · "+item.get("name",token),identifier=j.get("id"),title=j.get("title"),company=item.get("name",token),location=(j.get("location") or {}).get("name"),description=j.get("content"),url=j.get("absolute_url"),created=j.get("updated_at"))
def lever(item,out):
    slug=item["site"]
    url="https://api.lever.co/v0/postings/"+urllib.parse.quote(slug,safe="")+"?mode=json"
    for j in json.loads(fetch(url)):
        cats=j.get("categories") or {}
        desc=j.get("descriptionPlain") or j.get("description") or ""
        add(out,source="Lever · "+item.get("name",slug),identifier=j.get("id"),title=j.get("text"),company=item.get("name",slug),location=cats.get("location"),description=desc,url=j.get("hostedUrl"),contract=cats.get("commitment") or "")
def rss(item,out):
    root=ET.fromstring(fetch(item["url"]))
    entries=root.findall(".//item")
    atom=False
    if not entries:
        atom=True
        entries=root.findall(".//{http://www.w3.org/2005/Atom}entry")
    def val(e,name):
        node=e.find(name)
        return "".join(node.itertext()).strip() if node is not None else ""
    for e in entries:
        if atom:
            link=e.find("{http://www.w3.org/2005/Atom}link")
            href=link.get("href","") if link is not None else ""
            title=val(e,"{http://www.w3.org/2005/Atom}title")
            desc=val(e,"{http://www.w3.org/2005/Atom}summary") or val(e,"{http://www.w3.org/2005/Atom}content")
            date=val(e,"{http://www.w3.org/2005/Atom}updated")
        else:
            href=val(e,"link");title=val(e,"title")
            desc=val(e,"description");date=val(e,"pubDate")
        add(out,source=item.get("name","Flux emploi"),identifier=href,title=title,company=item.get("company",""),location=item.get("location",""),description=desc,url=href,created=date)
def adzuna(out):
    app_id=os.getenv("ADZUNA_APP_ID");key=os.getenv("ADZUNA_APP_KEY")
    if not (app_id and key):return False
    for term in TERMS:
        query=urllib.parse.urlencode({"app_id":app_id,"app_key":key,"what":term,"where":"Nantes","distance":35,"results_per_page":25})
        for j in json.loads(fetch("https://api.adzuna.com/v1/api/jobs/fr/search/1?"+query)).get("results",[]):
            add(out,source="Adzuna",identifier=j.get("id"),title=j.get("title"),company=(j.get("company") or {}).get("display_name"),location=(j.get("location") or {}).get("display_name"),description=j.get("description"),url=j.get("redirect_url"),created=j.get("created"))
    return True
def main():
    config=json.loads(CONFIG.read_text(encoding="utf-8"))
    offers={};errors=[];active=0
    # Garder la sélection manuelle existante tant que les annonces n’ont pas été vérifiées comme closes.
    if DEST.exists():
        try:
            previous=json.loads(DEST.read_text(encoding="utf-8"))
            for job in previous.get("offers",[]):
                if str(job.get("id","")).startswith("selection-"):
                    offers[job["id"]]=job
        except (OSError,ValueError,KeyError):pass
    for source in config.get("sources",[]):
        if not source.get("enabled",True):continue
        active+=1
        try:{"greenhouse":greenhouse,"lever":lever,"rss":rss}[source["type"]](source,offers)
        except Exception as exc:errors.append(source.get("name",source["type"])+": "+str(exc)[:180])
    if config.get("enable_adzuna",False):
        try:
            if adzuna(offers):active+=1
        except Exception as exc:errors.append("Adzuna: "+str(exc)[:180])
    if errors and active and not any(not k.startswith("selection-") for k in offers):
        print("Collecte automatique en échec ; conservation des anciennes données : "+"; ".join(errors))
        return
    if errors and not offers:
        print("Échec des sources ; conservation des anciennes données : "+"; ".join(errors))
        return
    if not active:
        print("Aucune source automatique configurée : conservation de la sélection existante.")
        return
    else:
        status="partial" if errors else "ok"
        msg="Certaines sources sont indisponibles : "+"; ".join(errors) if errors else ""
    output={"updated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"status":status,"message":msg,"sources_active":active,"offers":sorted(offers.values(),key=lambda x:(x["score"],x["created"]),reverse=True)}
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"{len(offers)} annonces · {active} sources actives · {len(errors)} erreurs")
if __name__=="__main__":main()
