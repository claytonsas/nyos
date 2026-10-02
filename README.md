# NYOS — site d'agence de sécurité offensive

Site vitrine statique, en HTML / CSS / JavaScript pur. Aucun build, aucune
dépendance à installer : on ouvre `index.html` et ça tourne.

**Direction artistique :** noir profond, accent vert terminal, typographie
Space Grotesk, animations au scroll. Inspiration Apple / Tesla, adaptée à un
univers cyber.

---

## Contenu

| Fichier | Rôle |
|---|---|
| `index.html` | Page principale : hero 3D, manifeste, scroll horizontal, slides pinnées, terminal, criticité, livrables, FAQ |
| `services.html` | Détail des six offres + cadre légal d'intervention |
| `contact.html` | Formulaire de cadrage + informations |
| `404.html` | Page d'erreur |
| `css/style.css` | Design system complet (tokens, composants, responsive) |
| `js/main.js` | Interactions : Lenis, GSAP, curseur, scroll horizontal, terminal, tilt, compteurs |
| `js/hero3d.js` | Sphère de particules WebGL (Three.js, module ES) |
| `bot/` | Bot de trading crypto (Python), indépendant du site, voir `bot/README.md` |

## Technos

Chargées par CDN, aucune installation :

- **GSAP 3.12** + **ScrollTrigger** — animations et scroll
- **Lenis 1.1** — défilement fluide
- **Three.js 0.160** — sphère de particules du hero (shaders GLSL maison)
- **Google Fonts** — Space Grotesk, Inter, JetBrains Mono

Tout dégrade proprement : sans WebGL, le hero garde son halo ; sans JavaScript,
le contenu reste lisible ; `prefers-reduced-motion` désactive les animations et
transforme les sections pinnées en sections classiques.

## Sections animées

- **Hero** — sphère de 8 000 particules déformée par un bruit simplex, réactive à
  la souris et au scroll, plus deux icosaèdres filaires.
- **Scroll horizontal** — les six services défilent latéralement pendant que la
  section reste épinglée.
- **Slides pinnées** — les cinq phases de la méthode se remplacent en place.
- **Terminal** — sortie tapée caractère par caractère, trois onglets.
- **Curseur personnalisé**, boutons magnétiques, cartes en tilt 3D, compteurs,
  marquee dont la vitesse suit le scroll, effet de décodage sur les titres.

---

## Lancer en local

```bash
# n'importe quel serveur statique — nécessaire pour les modules ES
python3 -m http.server 8000
# puis http://localhost:8000
```

Ouvrir directement le fichier en `file://` fonctionne aussi, sauf la sphère 3D
(les modules ES sont bloqués par la politique CORS des navigateurs).

## Publier sur GitHub Pages

1. Repo → **Settings** → **Pages**
2. *Source* : **Deploy from a branch**
3. *Branch* : `main`, dossier `/ (root)` → **Save**
4. Le site sort sur `https://claytonsas.github.io/nyos/` après une minute.

Le fichier `.nojekyll` est présent pour que GitHub serve les dossiers tels quels.

---

## À personnaliser

Ce sont les seuls endroits qui contiennent des valeurs de remplacement :

- **Email** — `contact@nyos.dev` apparaît dans les trois pages et dans
  `js/main.js` (fonction `forms`). Remplacer partout.
- **Formulaire** — il ouvre actuellement le client mail de l'utilisateur. Pour
  recevoir les demandes directement, brancher un service comme Formspree :
  ajouter `action="https://formspree.io/f/VOTRE_ID" method="POST"` sur le
  `<form id="contactForm">` et retirer l'appel `forms()` dans `main.js`.
- **Chiffres** — les compteurs de la page d'accueil (`data-count`) affichent des
  repères méthodologiques (OWASP Top 10, phases PTES, délai de rapport), pas un
  historique de missions. À remplacer par vos propres indicateurs si vous en avez.
- **Terminal** — les sorties de `js/main.js` (objet `scripts`) sont une
  démonstration illustrative, pas des logs réels.
- **Couleurs** — tout se règle dans `:root` en haut de `css/style.css`
  (`--accent`, `--accent-2`, `--bg`…).

## Licence

Code du site : libre d'usage pour NYOS. Marques et outils cités appartiennent à
leurs propriétaires respectifs.
