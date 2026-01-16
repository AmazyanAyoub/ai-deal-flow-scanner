import os
from datetime import datetime, timezone, timedelta
from github import Github, Auth
from database import DatabaseManager
from schemas import NormalizedProject, ProjectMetrics, ProductionSignals

class GitHubAdapter:
    def __init__(self):
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("❌ GITHUB_TOKEN manquant dans le .env")
        self.client = Github(auth=Auth.Token(token))
        self.db = DatabaseManager()
        
        # FIX 1: RESTORE FULL CLIENT KEYWORDS
        self.TARGET_KEYWORDS = [
            "agent", "orchestration", "inference", "rag", "eval",
            "workflow", "automation", "devtools", "infra", "observability"
        ]

    def fetch_candidates(self, scan_limit=10):
        # Broad scan for <90 days to capture potential candidates
        date_limit = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        query = f"ai OR agent OR llm created:>{date_limit}"
        
        print(f"🔎 [FETCHED] Querying GitHub: {query}")
        repos = self.client.search_repositories(query=query, sort="stars", order="desc")
        
        passed_to_ai, audit_log = [], []
        count = 0

        for repo in repos:
            if count >= scan_limit: 
                print(f"🛑 Scan limit of {scan_limit} reached. Stopping.")
                break
            
            # --- 1. IGNORE ALREADY JUDGED ---
            if self.db.is_judged(repo.html_url):
                # We already said Publish or Reject. Skip.
                print(f"   ⏭️  [SKIPPED] {repo.name} already judged.")
                continue 

            # --- 2. THE AGE GATE (7 to 90 Days) ---
            age_days = max(1, (datetime.now(timezone.utc) - repo.created_at).days)
            
            if age_days < 7:
                # Too young (Less than a week). Ignore.
                print(f"   ⏭️  [SKIPPED] {repo.name} too young ({age_days}d).")
                continue
            
            if age_days > 90:
                # Too old (Should be caught by query, but double checking).
                continue

            # --- 3. THE MEAN VELOCITY CHECK ---
            current_stars = repo.stargazers_count
            daily_average = current_stars / age_days
            
            if daily_average < 20:
                # Too slow. (e.g. 100 days old but only 500 stars = 5 stars/day)
                print(f"   ⏭️  [SKIPPED] {repo.name} too slow ({daily_average} stars/day).")
                continue
                
            # --- 4. KEYWORDS & QUALITY FILTER ---
            # If it passed the math, NOW we spend resources checking text.
            text_to_scan = (repo.name + " " + (repo.description or "")).lower()
            readme = self._get_readme(repo)
            full_text = text_to_scan + " " + readme.lower()
            
            if not any(k in full_text for k in self.TARGET_KEYWORDS):
                print(f"   ⏭️  [SKIPPED] {repo.name} missing target keywords.")
                continue 

            q_keywords = ["use case", "problem", "solution", "why", "example", "quickstart", "demo", "workflow"]
            kw_found = sum(1 for kw in q_keywords if kw in readme.lower())
            readme_ok = len(readme) >= 800 and kw_found >= 2
            
            if not readme_ok:
                print(f"   ⏭️  [SKIPPED] {repo.name} weak README.")
                continue

            # --- 5. SNAPSHOT & ACCEPT ---
            # It passed everything. We accept it NOW. 
            current_forks = repo.forks_count
            
            # Save history (for reference), but we don't wait.
            self.db.save_snapshot(repo.html_url, current_stars, current_forks)
            
            prod_data = self._extract_prod_signals(repo, readme)
            
            count += 1
            project = NormalizedProject(
                source="github",
                title=repo.name,
                description=repo.description,
                url=repo.html_url,
                metrics=ProjectMetrics(
                    stars_24h=int(daily_average), # We use Mean as the "Speed" metric now
                    stars_total=current_stars, 
                    forks_24h=0, # Not relevant in this logic
                    age_days=age_days,
                    last_commit_date=repo.pushed_at.replace(tzinfo=timezone.utc)
                ),
                signals=ProductionSignals(
                    has_docker=prod_data["has_docker"], 
                    has_ci=prod_data["has_ci"], 
                    production_signals=prod_data["production_signals"],
                    category_guess="pending",
                    category_confidence=0.0
                ),
                raw_text=readme[:3000]
            )
            passed_to_ai.append(project)
            print(f"   ✅ [SAVED] {repo.name} (Age: {age_days}d, Avg: {int(daily_average)} stars/day)")
            
            audit_log.append({"name": repo.name, "url": repo.html_url, "status": "Publish"})

        return passed_to_ai, audit_log

    def _get_readme(self, repo):
        try:
            return repo.get_readme().decoded_content.decode("utf-8")
        except:
            return ""

    def _extract_prod_signals(self, repo, readme):
        has_docker = False
        has_ci = False
        try:
            files = [f.path.lower() for f in repo.get_contents("")]
            has_docker = any("dockerfile" in f or "docker-compose" in f for f in files)
            try:
                repo.get_contents(".github/workflows")
                has_ci = True
            except: pass
        except: pass
        
        kws = ["production", "deploy", "self-hosted", "on-prem", "latency", "cost"]
        mentions = sum(1 for kw in kws if kw in readme.lower())
        total = int(has_docker) + int(has_ci) + mentions
        return {"has_docker": has_docker, "has_ci": has_ci, "production_signals": total}