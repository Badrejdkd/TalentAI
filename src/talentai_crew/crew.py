"""
Crew TalentAI — présélection RH en 4 agents (processus séquentiel).

  analyste_offre ─► evaluateur_cv ─► charge_prequalification ─► planificateur

Principe : l'IA RECOMMANDE, l'humain DÉCIDE. Les CV sont anonymisés avant tout appel au LLM
(@before_kickoff) et chaque proposition finale porte le statut « À valider par un recruteur ».
"""
import json
import os
import re

from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, before_kickoff, crew, task
from dotenv import load_dotenv

from talentai_crew.schemas import AnalyseOffre, EvaluationsLot, PlanningEntretiens, QuestionnairesLot
from talentai_crew.tools import CV_ANONYMISES, VerifierCompetencesTool, anonymiser

load_dotenv()

VALEURS_PAR_DEFAUT = {
    "experience_min": 0,
    "seuil_preselection": 70,
    "creneaux": "Aucun créneau fourni : propose des créneaux génériques à confirmer.",
    "type_entretien": "visioconférence",
    "lieu": "lien communiqué ultérieurement",
}


def get_llm(temperature: float = 0.2) -> LLM:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY manquante : copie .env.example en .env et renseigne ta clé.")
    return LLM(model=os.getenv("MODEL", "gpt-4o-mini"), temperature=temperature)


def _lire_cvs(cvs) -> list[dict]:
    """Accepte une liste [{id, texte}], du JSON, ou du texte brut séparé par des lignes '====='."""
    if isinstance(cvs, str):
        try:
            cvs = json.loads(cvs)
        except json.JSONDecodeError:
            blocs = [b.strip() for b in re.split(r"\n\s*={3,}\s*\n", cvs) if b.strip()]
            cvs = [{"texte": b} for b in blocs]
    liste = []
    for i, cv in enumerate(cvs, start=1):
        texte = cv["texte"] if isinstance(cv, dict) else str(cv)
        liste.append({"id": (cv.get("id") if isinstance(cv, dict) else None) or f"C{i:02d}", "texte": texte})
    return liste


@CrewBase
class TalentAICrew:
    """Présélection RH multi-agents."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # ------------------------------------------------------------------ hooks
    @before_kickoff
    def preparer_entrees(self, inputs: dict) -> dict:
        """Anonymise les CV et complète les entrées facultatives."""
        for k, v in VALEURS_PAR_DEFAUT.items():
            inputs.setdefault(k, v)
        CV_ANONYMISES.clear()
        blocs = []
        for cv in _lire_cvs(inputs.get("cvs", [])):
            anonyme = anonymiser(cv["texte"])
            CV_ANONYMISES[cv["id"]] = anonyme
            blocs.append(f"[{cv['id']}]\n{anonyme}")
        if not blocs:
            raise ValueError("Aucun CV fourni dans l'entrée 'cvs'.")
        inputs["cvs_anonymises"] = "\n\n-----\n\n".join(blocs)
        inputs["nb_candidats"] = len(blocs)
        inputs.pop("cvs", None)  # les données personnelles ne sont jamais transmises aux agents
        return inputs

    # ----------------------------------------------------------------- agents
    @agent
    def analyste_offre(self) -> Agent:
        return Agent(config=self.agents_config["analyste_offre"], llm=get_llm(0.1), verbose=True)

    @agent
    def evaluateur_cv(self) -> Agent:
        return Agent(
            config=self.agents_config["evaluateur_cv"],
            tools=[VerifierCompetencesTool()],
            llm=get_llm(0.0),
            max_iter=25,
            verbose=True,
        )

    @agent
    def charge_prequalification(self) -> Agent:
        return Agent(config=self.agents_config["charge_prequalification"], llm=get_llm(0.4), verbose=True)

    @agent
    def planificateur(self) -> Agent:
        return Agent(config=self.agents_config["planificateur"], llm=get_llm(0.3), verbose=True)

    # ------------------------------------------------------------------ tasks
    @task
    def analyse_offre_task(self) -> Task:
        return Task(config=self.tasks_config["analyse_offre_task"], output_pydantic=AnalyseOffre)

    @task
    def evaluation_cvs_task(self) -> Task:
        return Task(
            config=self.tasks_config["evaluation_cvs_task"],
            output_pydantic=EvaluationsLot,
            # HUMAN_REVIEW=true : le recruteur relit la notation et peut la faire corriger
            human_input=os.getenv("HUMAN_REVIEW", "false").lower() == "true",
        )

    @task
    def prequalification_task(self) -> Task:
        return Task(config=self.tasks_config["prequalification_task"], output_pydantic=QuestionnairesLot)

    @task
    def planification_task(self) -> Task:
        return Task(config=self.tasks_config["planification_task"], output_pydantic=PlanningEntretiens)

    # ------------------------------------------------------------------- crew
    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
