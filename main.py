import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from src.github_adapter import GitHubAdapter
from src.judge import JudgeAgent

from src.utils import log_saver
log_saver.start_logging()
# 1. Chargement des variables d'environnement (.env)
load_dotenv()

def run_pipeline():
    print(f"🚀 INVESTMENT RADAR START - {datetime.now()}")
    
    # Vérification des clés API
    if not os.getenv("GITHUB_TOKEN") or not os.getenv("GROQ_API_KEY"):
        print("❌ ERREUR : Clés API manquantes dans le fichier .env")
        return

    adapter = GitHubAdapter()
    judge = JudgeAgent()
    
    # 2. FETCHED : Scan initial (Point 10)
    # On récupère les candidats qui ont passé les filtres Hard (Age, README, Growth)
    candidates, audit_log = adapter.fetch_candidates(scan_limit=10)
    
    print(f"\n🔎 [SAVED] {len(candidates)} projets sélectionnés pour analyse IA")
    print("-" * 50)
    
    final_deals = []

    # 3. Évaluation IA (Point 8)
    for i, project in enumerate(candidates):
        print(f"⚖️ Judging {project.title} ({project.url})...")
        
        verdict = judge.evaluate(project)
        
        if verdict:
            # Calcul de la condition de passage (Point 8)
            # Règle : novelty + market_leverage + moat_potential >= 18
            score_investment = verdict.novelty + verdict.market_leverage + verdict.moat_potential
            
            # Affichage du score pour le debug (Visibilité totale)
            print(f"      📊 Score: {score_investment}/30")
            print(f"      📝 Note: N:{verdict.novelty} | M:{verdict.market_leverage} | P:{verdict.moat_potential}")
            print(f"      🚩 Flags: {', '.join(verdict.reject_flags) if verdict.reject_flags else 'None'}")

            # Enregistrement en Base de données (Mémoire)
            decision = "PUBLISH" if score_investment >= 18 else "REJECT"
            adapter.db.mark_processed(project, decision, score_investment)

            if decision == "PUBLISH":
                print(f"🔥 [DEAL FOUND] {project.title} validé !")
                
                # 4. PREVIEW POST (Point 9) - Affichage du post en Russe
                print(f"\n--- PREVIEW POST (RUSSIAN) ---")
                print(verdict.preview_post)
                print("-" * 30 + "\n")
                
                final_deals.append({
                    "project": project.model_dump(mode='json'),
                    "verdict": verdict.model_dump(mode='json'),
                    "total_score": score_investment
                })
            else:
                print(f"      👎 REJECTED: {verdict.one_line_reason}")
            
            # 5. Sécurité Rate Limit (Point 10)
            # Pause de 12 secondes entre chaque appel IA pour éviter l'erreur 429
            if i < len(candidates) - 1:
                print(f"      ⏳ Waiting 12s for next evaluation...")
                time.sleep(12)
        else:
            print(f"      ⚠️ IA failed to return a valid verdict for {project.title}")

    # 6. SAUVEGARDE DU RAPPORT FINAL (Point 7 & 10)
    report = {
        "timestamp": str(datetime.now()),
        "summary": {
            "total_fetched": len(audit_log),
            "passed_hard_filters": len(candidates),
            "new_deals_found": len(final_deals)
        },
        "deals": final_deals,
        "audit": audit_log
    }

    filename = "final_delivery.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ PIPELINE COMPLETE")
    print(f"📁 Rapport généré : {filename}")
    print(f"🎯 Deals trouvés : {len(final_deals)}")

if __name__ == "__main__":
    try:
        run_pipeline()
    except KeyboardInterrupt:
        print("\n🛑 Pipeline arrêté par l'utilisateur.")
    except Exception as e:
        print(f"\n💥 Erreur fatale : {e}")