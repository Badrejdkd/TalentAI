# TalentAI Crew — présélection RH multi-agents (CrewAI)

Version **CrewAI native** du projet TalentAI : 4 agents, processus séquentiel, déployable sur **CrewAI AMP** (app.crewai.com).

> **L'IA recommande, l'humain décide.** Les CV sont anonymisés *avant* d'être transmis aux agents
> (hook `@before_kickoff`) et chaque proposition d'entretien porte le statut « À valider par un recruteur ».

## Les agents

| # | Agent | Tâche | Sortie (Pydantic) |
|---|---|---|---|
| 1 | `analyste_offre` | Grille d'évaluation pondérée + alertes de biais | `AnalyseOffre` |
| 2 | `evaluateur_cv` | Note chaque CV anonymisé avec justification (outil `verifier_competences_cv`) | `EvaluationsLot` |
| 3 | `charge_prequalification` | Questionnaire pour chaque candidat ≥ seuil | `QuestionnairesLot` |
| 4 | `planificateur` | Créneau distinct + e-mail d'invitation + guide d'entretien | `PlanningEntretiens` |

LangChain est utilisé pour lire les CV (PyPDFLoader, Docx2txtLoader, TextLoader) ; le LLM est ChatGPT (`MODEL`, par défaut `gpt-4o-mini`).

## Lancer en local

```powershell
cd talentai_crew
copy .env.example .env        # puis renseigner OPENAI_API_KEY
pip install uv                # si uv n'est pas installé
crewai install                # crée .venv à partir de uv.lock
crewai run                    # lance l'exemple du dossier exemples/
```

Avec tes propres données : `uv run talentai_crew C:\chemin\vers\mon_dossier`
(le dossier contient `offre.txt`, `cvs\` avec des PDF/DOCX/TXT, et éventuellement `creneaux.txt`).

Résultats dans `sortie/` : `rapport_preselection.md` (à relire et signer) et `resultats_preselection.json`.

Relecture humaine dans le terminal : `HUMAN_REVIEW=true` dans `.env` — la crew s'arrête après la notation des CV
pour que le recruteur valide ou demande une correction.

## Déployer sur CrewAI AMP

```powershell
crewai login                  # connexion à app.crewai.com
git init; git add .; git commit -m "TalentAI crew"
# créer un dépôt GitHub (privé) puis :
git remote add origin https://github.com/<toi>/talentai_crew.git
git push -u origin main
crewai deploy validate        # vérifie le projet avant déploiement
crewai deploy create          # lit .env et crée le déploiement (OPENAI_API_KEY, MODEL)
crewai deploy status          # attendre « Online » (≈ 5-10 min au 1er déploiement)
crewai deploy push            # après chaque modification poussée sur GitHub
crewai deploy logs            # en cas d'erreur
```

### Entrées de la crew (API / interface AMP)

| Entrée | Obligatoire | Exemple |
|---|---|---|
| `offre_titre` | oui | `Data Scientist confirmé(e)` |
| `offre_description` | oui | texte complet de l'offre |
| `cvs` | oui | JSON `[{"id":"C01","texte":"..."}]` **ou** textes séparés par une ligne `=====` |
| `experience_min` | non | `3` |
| `seuil_preselection` | non | `70` |
| `creneaux` | non | `lundi 5/10 09:00 ; lundi 5/10 10:00 ; ...` |
| `type_entretien`, `lieu` | non | `visioconférence`, `https://meet.google.com/...` |

Appel de l'API une fois déployée (URL et jeton dans l'onglet *Status* de la crew) :

```bash
curl -X POST https://<ta-crew>.crewai.com/kickoff \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"inputs": {"offre_titre": "Data Scientist", "offre_description": "...", "cvs": "CV 1...\n=====\nCV 2..."}}'
# puis GET https://<ta-crew>.crewai.com/status/<kickoff_id>
```

## Structure

```
talentai_crew/
├── pyproject.toml · uv.lock · .env.example
├── exemples/                 offre.txt, cvs/, creneaux.txt
└── src/talentai_crew/
    ├── config/agents.yaml    les 4 agents
    ├── config/tasks.yaml     les 4 tâches (avec context)
    ├── crew.py               @CrewBase + @before_kickoff (anonymisation)
    ├── schemas.py            sorties structurées
    ├── tools/rh_tools.py     LangChain loaders, anonymisation, outil de vérification
    └── main.py               run / train / replay / test / run_with_trigger
```
