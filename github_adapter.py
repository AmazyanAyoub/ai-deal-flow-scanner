import os
from datetime import datetime, timezone
from typing import List
from github import Github, Auth
from dotenv import load_dotenv

# Import our tools
from schemas import NormalizedProject, ProjectMetrics, ProductionSignals
from database import DatabaseManager

load_dotenv()

class GitHubAdapter:
    def __init__(self):
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN not found in .env file")
        
        self.client = Github(auth=Auth.Token(token))
        self.db = DatabaseManager()

        # --- CLIENT CONFIGURATION ---
        
        # 1. Broad Search Query (Client Section 3: Languages)
        # We capture everything first, then filter strictly below.
        self.SEARCH_QUERY = "topic:ai language:python"
        
        # 2. Target Keywords (Client Section 3)
        # Must appear in Name, Description, or README
        self.TARGET_KEYWORDS = [
            "agent", "orchestration", "inference", "rag", "eval",
            "workflow", "automation", "devtools", "infra", "observability"
        ]
        
        # 3. Readme Quality Keywords (Client Section 5.2)
        self.README_KEYWORDS = [
            "use case", "problem", "solution", "why", "example", 
            "quickstart", "demo", "workflow"
        ]
        
        # 4. Production Signal Keywords (Client Section 6.2)
        self.PROD_KEYWORDS = ["production", "deploy", "self-hosted", "on-prem", "latency", "cost"]

    def fetch_candidates(self, limit: int = 10) -> List[NormalizedProject]:
        """
        Main Loop: Search -> Strict Filters (5.1 - 5.4) -> Signals -> Normalize
        """
        print(f"🔎 Searching GitHub (Query: {self.SEARCH_QUERY})...")
        
        # Note: 'sort' is passed here to fix the previous API error
        results = self.client.search_repositories(
            query=self.SEARCH_QUERY, 
            sort="updated", 
            order="desc"
        )
        
        candidates = []
        count = 0
        
        for repo in results:
            if count >= limit:
                break
            
            print(f"\n👀 Checking: {repo.name} ({repo.stargazers_count} stars)")

            # --- 1. KEYWORD FILTER (Client Section 3) ---
            # Check Name and Description first (fastest)
            text_to_scan = (repo.name + " " + (repo.description or "")).lower()
            if not any(k in text_to_scan for k in self.TARGET_KEYWORDS):
                # If not in name/desc, we will check README later as a last resort
                keywords_found_in_meta = False
            else:
                keywords_found_in_meta = True

            # --- 2. AGE FILTER (Client Section 5.1) ---
            # Rule: age_days <= 90
            created_at = repo.created_at.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - created_at).days
            
            if age_days > 90:
                print(f"   🚫 Reject: Too old ({age_days} days)")
                continue

            # --- 3. DYNAMICS & FALLBACK (Client Section 4) ---
            # Save snapshot
            self.db.save_snapshot(repo.html_url, repo.stargazers_count)
            # Calculate 24h growth
            stars_growth, is_real_data = self.db.get_growth_stats(repo.html_url, repo.stargazers_count)
            
            # FALLBACK LOGIC: If no 24h history (Day 1), use Total Stars as proxy for filtering
            effective_growth = stars_growth if is_real_data else repo.stargazers_count
            if not is_real_data:
                print(f"   ℹ️ First run: Using total stars ({effective_growth}) as growth proxy.")

            # --- 4. ACTIVITY FILTER (Client Section 5.4) ---
            # Rule: last_commit <= 14 days OR stars_last_24h >= 30
            last_pushed = repo.pushed_at.replace(tzinfo=timezone.utc)
            days_since_push = (datetime.now(timezone.utc) - last_pushed).days
            
            is_active = days_since_push <= 14
            is_viral = effective_growth >= 30
            
            if not (is_active or is_viral):
                print(f"   🚫 Reject: Inactive ({days_since_push}d) and not viral ({effective_growth} stars)")
                continue

            # --- 5. README & CONTENT FILTER (Client Section 5.2) ---
            readme_content = self._get_readme(repo)
            
            # A. Check Meaningful (Length > 800 + Keywords)
            if not self._is_readme_meaningful(readme_content):
                print(f"   🚫 Reject: Readme too short or weak")
                continue
            
            # B. Final Keyword Check (if missed in Name/Desc)
            if not keywords_found_in_meta:
                if not any(k in readme_content.lower() for k in self.TARGET_KEYWORDS):
                    print(f"   🚫 Reject: No target keywords (agent, rag, etc.) found anywhere")
                    continue

            # --- 6. PRODUCTION SIGNALS (Client Section 6.2) ---
            signals = self._extract_production_signals(repo, readme_content)

            # --- 7. GROWTH FILTER (Client Section 5.3) ---
            # Rule: Growth >= 20 OR (Growth >= 10 AND Signals >= 2)
            # has_high_growth = effective_growth >= 20
            # has_med_growth_pro = (effective_growth >= 10 and signals.production_signals_count >= 2)
            
            # if not (has_high_growth or has_med_growth_pro):
            #     print(f"   🚫 Reject: Low growth ({effective_growth}) & low signals")
            #     continue

            # --- ✅ PASSED ALL FILTERS ---
            print(f"   ✅ CANDIDATE ACCEPTED!")
            
            candidate = NormalizedProject(
                id=repo.html_url,
                source="github",
                title=repo.name,
                url=repo.html_url,
                description=repo.description,
                created_at=created_at,
                metrics=ProjectMetrics(
                    stars_24h=stars_growth, # Report REAL growth (0 on day 1), not proxy
                    stars_total=repo.stargazers_count,
                    forks_24h=0,
                    age_days=age_days,
                    last_commit_date=last_pushed
                ),
                signals=signals,
                raw_text=f"README:\n{readme_content[:3000]}\n\nFILE STRUCTURE:\n{str(self._get_file_structure(repo))}"
            )
            
            candidates.append(candidate)
            count += 1

        return candidates

    # --- HELPER METHODS ---

    def _get_readme(self, repo) -> str:
        try:
            return repo.get_readme().decoded_content.decode("utf-8")
        except:
            return ""

    def _is_readme_meaningful(self, content: str) -> bool:
        if len(content) < 800:
            return False
        found = [kw for kw in self.README_KEYWORDS if kw in content.lower()]
        return len(found) >= 2

    def _extract_production_signals(self, repo, readme_content: str) -> ProductionSignals:
        files = self._get_file_structure(repo)
        text = readme_content.lower()
        
        has_docker = any("docker" in f.lower() for f in files)
        has_ci = any(".github/workflows" in f or ".circleci" in f for f in files)
        keyword_count = sum(1 for kw in self.PROD_KEYWORDS if kw in text)
        
        total = int(has_docker) + int(has_ci) + keyword_count
        
        return ProductionSignals(
            has_docker=has_docker,
            has_ci=has_ci,
            production_signals_count=total,
            category_guess="other",
            category_confidence=0.0
        )

    def _get_file_structure(self, repo) -> List[str]:
        try:
            return [c.path for c in repo.get_contents("")]
        except:
            return []