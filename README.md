# Trailendar

Site statique (`index.html`) qui lit `trails.json`. Un crawler (GitHub Actions) met ce fichier à jour, Netlify redéploie à chaque mise à jour.

## Mise en ligne, étape par étape
1. **GitHub** : crée un dépôt et envoie-y TOUT le contenu de ce dossier, dossier caché `.github` compris (utilise `git` ou GitHub Desktop : l'envoi par navigateur oublie parfois les dossiers cachés).
2. **Clé Firecrawl** : crée une clé API sur firecrawl.dev. Dans le dépôt : *Settings → Secrets and variables → Actions → New repository secret*, nom `FIRECRAWL_API_KEY`.
3. **Netlify** : *Add new site → Import an existing project* → choisis ton dépôt GitHub. Build command : vide. Publish directory : `.` (déjà dans `netlify.toml`).
4. **Premier test du crawler** : dans `.github/workflows/crawl.yml`, ajoute sous `env:` la ligne `ONLY_DEPS: "73"` (un seul département), puis *Actions → Crawl des trails → Run workflow*. Contrôle `trails.json` et `crawl-report.json`. Si tout va bien, retire la ligne pour passer aux 101 départements.

## Fonctionnement
- **Chaque lundi (et au lancement manuel)** : découverte des trails de chaque département.
- **Chaque nuit** : rafraîchissement des fiches connues, selon la proximité de la course (moins de 60 jours : tous les jours ; jusqu'à 6 mois : chaque semaine ; au-delà : chaque mois).
- `MAX_EVENTS` (150 par défaut, dans le workflow) plafonne le nombre de fiches lues par exécution, donc ta consommation Firecrawl.
- Une date d'inscription n'est marquée « communiquée » que si elle est écrite sur la page. Sinon : « Inconnu ».
- Les 27 événements de Haute-Savoie fournis sont marqués `manual` : le crawler ne les écrase pas.

## À vérifier avant la mise en production
- **Doc Firecrawl** : le script utilise l'API v1 (`/v1/scrape` avec extraction JSON). Vérifie les noms de champs dans leur documentation actuelle.
- **Adresses des listes** : le script devine l'adresse de chaque département sur milesrepublic.com (`/trail/<nom-du-département>`). Les départements dont l'adresse est fausse apparaissent dans `crawl-report.json` → `listing_errors`. À corriger au fur et à mesure.
- **Conditions d'utilisation** de chaque source (milesrepublic, sites des courses) et `robots.txt` : à vérifier avant un crawl complet.
- **Logos** : non récupérés (image par défaut). Les logos officiels sont protégés.
- **Carte** : fond de carte @svg-maps/france.departments (CC BY 4.0), mention à conserver.

## Aperçu local
`python3 -m http.server` dans ce dossier, puis http://localhost:8000 (ouvrir `index.html` directement ne marche pas : le navigateur bloque la lecture de `trails.json`).
