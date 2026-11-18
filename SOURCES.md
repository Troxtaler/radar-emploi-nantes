# Radar Emploi Nantes — collecte multi-source

Le tableau de bord est publié sur GitHub Pages. La page `offres.html` affiche les annonces collectées dans `data/offres.json`, sans renvoyer l'utilisateur vers les plateformes pour lire la description disponible.

## Sources compatibles

- **Greenhouse Job Board API** : endpoint public pour les entreprises qui utilisent Greenhouse, avec un identifiant de tableau `board_token`.
- **Lever Postings API** : annonces publiques des entreprises équipées de Lever, avec un identifiant `site`.
- **RSS/Atom** : flux publics d'offres dont les conditions permettent cette utilisation.
- **Adzuna** : facultatif, désactivé par défaut, avec secrets GitHub `ADZUNA_APP_ID` et `ADZUNA_APP_KEY`.

Les flux ne sont **pas** préconfigurés : aucun employeur ni identifiant de flux n'est supposé sans vérification. La collecte n'extrait pas automatiquement les pages Indeed, LinkedIn ou Welcome to the Jungle et ne contourne pas leurs restrictions.

## Ajouter une entreprise

Dans `sources.json`, renseigner une source vérifiée. Exemple de format (valeurs fictives à remplacer) :

```json
{
  "enable_adzuna": false,
  "sources": [
    {"type": "greenhouse", "name": "Entreprise exemple", "board_token": "identifiant-verifie", "enabled": true},
    {"type": "lever", "name": "Autre entreprise", "site": "identifiant-verifie", "enabled": true},
    {"type": "rss", "name": "Flux officiel", "url": "https://exemple.fr/jobs.xml", "company": "Entreprise exemple", "location": "Nantes", "enabled": true}
  ]
}
```

Une tâche GitHub Actions lance `python scripts/collect_offers.py` plusieurs fois par jour et publie le fichier JSON. Le filtrage géographique est fondé sur le texte de localisation, et non sur un calcul exact du temps de trajet ; le score est heuristique, pas une estimation statistique de recrutement. Les descriptions sont celles exposées par les sources, parfois abrégées.

En l'absence de sources configurées, le site signale explicitement qu'aucune collecte n'est active.
