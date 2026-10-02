# NYOS Trader — bot crypto long / short

Bot de trading sur futures perpétuels (BTC, ETH…), en long et en short, avec levier
plafonné. Il tourne 24 h/24 sur un serveur (Oracle Cloud gratuit) et se pilote depuis
Telegram.

> **À lire avant tout.** Aucun bot ne garantit un gain, ni 35 € par jour ni autre chose.
> Celui-ci applique des règles strictes, sans émotion, et coupe les pertes. Il peut
> perdre de l'argent. Le levier multiplie les gains **et** les pertes. Le parcours
> obligatoire est donc : **backtest → paper trading (argent fictif) 2 à 4 semaines →
> réel avec un petit montant.**

## La stratégie

Suivi de tendance avec entrée sur cassure. C'est une des approches les plus robustes et
les plus documentées sur la crypto, qui évolue par grosses tendances.

| Règle | Long | Short |
|---|---|---|
| Tendance | EMA 50 > EMA 200 et prix > EMA 200 | EMA 50 < EMA 200 et prix < EMA 200 |
| Force | ADX ≥ 20 (pas de trade en marché plat) | idem |
| Déclencheur | clôture au-dessus du plus haut des 20 dernières bougies | clôture sous le plus bas des 20 dernières bougies |
| Stop-loss | entrée − 2 × ATR | entrée + 2 × ATR |
| Objectif | 2 × le risque | 2 × le risque |

Unité de temps par défaut : **1 h**. Le scalping en 1 ou 5 minutes paie des frais sur
chaque trade, et ces frais mangent presque toujours le gain d'un particulier.

## La gestion du risque (le plus important)

- **1 % du capital risqué par trade.** Si le stop est touché, tu perds environ 1 %, frais
  compris. La taille de position est calculée pour ça.
- **Levier plafonné à 3×** en marge isolée. Le levier n'est qu'une conséquence de la taille
  calculée, jamais un multiplicateur aveugle. Le bot refuse tout trade dont le stop serait
  trop proche du prix de liquidation.
- **Stop et objectif posés chez l'exchange** dès l'entrée : si le serveur plante, la
  position reste protégée. Si le stop ne peut pas être posé, la position est refermée
  immédiatement.
- **Perte max de 3 % par jour** : au-delà, plus de nouveaux trades jusqu'au lendemain.
- **2 positions max** en même temps.

## Ce que ça donne avec tes 35 €/jour

Le backtest affiche le PnL moyen par jour **et le capital qu'il faudrait** pour faire
35 €/jour au rythme mesuré. C'est la vraie question : 35 €/jour avec 1 000 € de capital
voudrait dire +3,5 % par jour, ce qu'aucune stratégie sérieuse ne tient.

## Installation locale

```bash
cd bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp .env.example .env
```

### 1. Backtest sur les vraies données (sans compte, sans clé API)

```bash
python -m trader backtest --days 730
```

Télécharge 2 ans d'historique, simule chaque trade avec les frais, le glissement et le
funding, puis affiche le résultat. Le détail est écrit dans `data/backtest_trades.csv` et
`data/backtest_jours.csv`. Tu peux aussi passer tes propres CSV (`--csv fichier.csv`).
`--demo` utilise des données **fictives**, uniquement pour vérifier que le code tourne.

**Ne passe à l'étape suivante que si** le profit factor dépasse 1,3, le drawdown max
te paraît supportable, et le résultat tient sur plusieurs périodes et plusieurs paires.

### 2. Paper trading (vrais prix, argent fictif)

`mode: paper` dans `config.yaml`, puis :

```bash
python -m trader run
```

Le bot suit le marché en direct et simule les ordres. Journal : `data/trades_paper.csv`.
Laisse-le tourner **au moins 2 à 4 semaines**.

### 3. Réel

1. Crée une clé API sur l'exchange : **lecture + trading futures uniquement, retrait
   désactivé**, restreinte à l'IP de ton serveur.
2. Mets-la dans `.env`, ajoute `CONFIRM_LIVE=OUI`, et passe `mode: live`.
3. Commence avec un **petit montant** que tu peux perdre.

Vérifie aussi que l'exchange propose bien les futures perpétuels aux résidents de ton pays
et qu'il y est autorisé (en France : enregistrement AMF / agrément MiCA). Pour tester les
ordres sans risque, beaucoup d'exchanges ont un testnet (`testnet: true`).

## Telegram

1. Crée un bot avec **@BotFather** et récupère le token.
2. Récupère ton identifiant avec **@userinfobot**.
3. Mets `TELEGRAM_TOKEN` et `TELEGRAM_CHAT_ID` dans `.env`, et `telegram.enabled: true`.

Tu reçois chaque entrée, chaque sortie avec son PnL, et un bilan quotidien. Commandes :

| Commande | Effet |
|---|---|
| `/status` | capital, PnL du jour, positions ouvertes |
| `/pnl` | PnL des 7 derniers jours |
| `/pause` | plus de nouvelles entrées (les stops restent actifs) |
| `/resume` | reprise |
| `/stop` | ferme tout et met en pause |

Seul ton chat est écouté : les messages venant de quelqu'un d'autre sont ignorés.

## Hébergement sur Oracle Cloud (gratuit)

1. Crée un compte Oracle Cloud et une instance **Always Free** (Ubuntu, forme Ampere A1 ARM).
   Choisis une région européenne (Paris, Francfort…) : certains exchanges bloquent les IP
   américaines.
2. Connecte-toi en SSH avec une clé, copie le dossier `bot/`, puis :

```bash
sudo bash deploy/install-oracle.sh
sudo nano /opt/nyos-bot/config.yaml
sudo nano /opt/nyos-bot/.env
sudo systemctl start nyos-bot
journalctl -u nyos-bot -f
```

Le script crée un utilisateur système dédié, installe le bot dans un environnement Python
isolé et active un pare-feu (SSH seulement). Il active aussi les mises à jour de sécurité
automatiques et un service systemd durci qui redémarre le bot s'il plante. L'état est
sauvegardé dans `data/`, donc un redémarrage reprend où le bot en était.

Avec Docker à la place :

```bash
docker build -t nyos-bot .
docker run -d --restart=always --name nyos-bot \
  -v $PWD/config.yaml:/app/config.yaml:ro -v $PWD/.env:/app/.env:ro \
  -v $PWD/data:/app/data nyos-bot
```

## Structure

| Fichier | Rôle |
|---|---|
| `trader/strategy.py` | règles d'entrée, stop et objectif |
| `trader/risk.py` | taille de position, levier, liquidation |
| `trader/portfolio.py` | exécutions simulées (backtest et paper) |
| `trader/backtest.py` | backtest et statistiques |
| `trader/live.py` | boucle temps réel, broker paper et broker live |
| `trader/notify.py` | Telegram |
| `trader/data.py` | historique via ccxt, CSV, données fictives |

## Tests

```bash
pip install pytest && python -m pytest -q tests
```

Ils couvrent les indicateurs, la taille de position, le levier et la liquidation, ainsi que
le stop supposé touché en premier quand une bougie touche stop et objectif. Ils vérifient
l'absence de biais du futur dans le backtest, le paper trading de bout en bout avec reprise
après redémarrage, et les ordres live (stop chez l'exchange, fermeture d'urgence) contre un
exchange simulé.
