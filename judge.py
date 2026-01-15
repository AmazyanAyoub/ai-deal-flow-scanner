import os
import json
from datetime import datetime
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

# Import our updated structures
from schemas import NormalizedProject, JudgeOutput
from github_adapter import GitHubAdapter

load_dotenv()

class JudgeAgent:
    def __init__(self):
        # 1. Setup the LLM (Groq Llama 3 for speed, or GPT-4o for precision)
        if os.getenv("GROQ_API_KEY"):
            print("🧠 Loading Judge with Groq (Llama-3.3-70b)...")
            self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        else:
            print("🧠 Loading Judge with OpenAI (GPT-4o)...")
            self.llm = ChatOpenAI(model="gpt-4o", temperature=0)

        # 2. Setup the Parser (Enforces the 5-point scorecard)
        self.parser = PydanticOutputParser(pydantic_object=JudgeOutput)

        # 3. Define the FULL VC Prompt
        # 3. Define the VC Prompt (Russian Analyst Edition)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are a strict AI Venture Capitalist writing for a top-tier Russian tech channel. 
            Your job is to evaluate projects and write a deep, analytical investment memo in Russian.

            ### YOUR SCORING CRITERIA (0-10)
            1. NOVELTY: Is this a new approach? (0=Copy/Wrapper, 10=Groundbreaking)
            2. MARKET LEVERAGE: Is the market huge? (0=Niche/Toy, 10=Global B2B/Infra)
            3. MOAT POTENTIAL: Is it hard to copy? (0=Simple Script, 10=Deep Tech/Complex)
            4. EXECUTION SIGNAL: Is the engineering elite? (Look at file structure, Docker, tests)
            5. TIME TO MARKET: Is it ready now?

            ### YOUR TASKS
            1. **Classify**: Pick category & confidence.
            2. **Score**: Assign integer scores (0-10).
            3. **Draft the Post (REQUIRED)**: 
               - Write the post in **RUSSIAN** (Русский язык).
               - Strict "Deep Analysis" tone. No marketing fluff.
               - Follow the structure below EXACTLY.

            ### POST TEMPLATE (RUSSIAN)
            
            **[Unique Startup], {title} -- [One sentence hook about the core problem]**

            **Вкратце:**
            [2 sentences about the market problem. E.g. "Everyone builds agents, but no one has tools..."]

            **{title} предлагает другой подход:**
            [What this project actually does. The solution.]

            **Почему это важно:**
            – [Bullet 1: Market trend]
            – [Bullet 2: Why this solves pain]
            
            **Где здесь потенциал:**
            – [Bullet 1: Use case]
            – [Bullet 2: Who will buy this?]

            **Честный риск:**
            [1 sentence about the main weakness/risk (e.g., complexity, stability, competition).]

            ---
            
            4. **Decide**:
               - Calculate SUM = Novelty + Market + Moat.
               - IF SUM >= 18: final_decision="PUBLISH"
               - IF SUM < 18: final_decision="REJECT"
            """),
            ("human", """
            Analyze this project:
            Title: {title}
            Description: {description}
            URL: {url}
            
            Hard Metrics:
            - Stars: {stars_total} (+{stars_24h} today)
            - Age: {age_days} days
            
            Production Signals:
            - Docker: {has_docker}, CI: {has_ci}
            - Score: {prod_score}
            
            Raw Content:
            {raw_text}
            
            {format_instructions}
            """)
        ])

        self.chain = self.prompt | self.llm | self.parser

    def evaluate(self, project: NormalizedProject) -> JudgeOutput:
        print(f"⚖️  VC Judging {project.title}...")
        try:
            result = self.chain.invoke({
                "title": project.title,
                "description": project.description,
                "url": str(project.url),
                "stars_total": project.metrics.stars_total,
                "stars_24h": project.metrics.stars_24h,
                "age_days": project.metrics.age_days,
                "has_docker": project.signals.has_docker,
                "has_ci": project.signals.has_ci,
                "prod_score": project.signals.production_signals_count,
                "raw_text": project.raw_text[:4000], # Limit context
                "format_instructions": self.parser.get_format_instructions()
            })
            
            # --- LOGIC OVERRIDE: Enforce Client's Math Rule ---
            # Rule: Novelty + Market + Moat >= 18
            core_score = result.novelty + result.market_leverage + result.moat_potential
            
            print(f"   📊 Scorecard: N={result.novelty} M={result.market_leverage} M={result.moat_potential} (Sum={core_score})")
            
            # Map AI Classification to Project Object
            project.signals.category_guess = result.category_guess
            project.signals.category_confidence = result.category_confidence
            
            # Decision Logic
            if core_score >= 18:
                result.final_decision = "PUBLISH"
                # The preview_post is GUARANTEED to exist because of the Schema + Prompt
                print(f"   ✅ PASSED! (Score {core_score} >= 18)")
            else:
                result.final_decision = "REJECT"
                result.preview_post = None # We discard the draft because it failed the math
                print(f"   ❌ REJECTED (Score {core_score} < 18)")
                
            return result
            
        except Exception as e:
            print(f"❌ Error evaluating {project.title}: {e}")
            return None

# --- Main Execution Flow (Test) ---
if __name__ == "__main__":
    # 1. Run Adapter (With new Hard Filters)
    adapter = GitHubAdapter()
    
    # Fetch 2 projects for testing
    projects = adapter.fetch_candidates(limit=2) 
    
    # 2. Run Judge
    judge = JudgeAgent()
    
    full_report = []
    
    print("\n\n📊 --- FINAL VC REPORT ---")
    for project in projects:
        verdict = judge.evaluate(project)
        
        if verdict:
            full_report.append({
                "project": project.model_dump(mode='json'),
                "verdict": verdict.model_dump(mode='json')
            })
            
            if verdict.final_decision == "PUBLISH":
                print(f"\n📢 DRAFT POST:\n{verdict.preview_post}")
                print("-" * 60)

    # Save to JSON (Client Requirement Section 7 Format)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    with open(f"final_output_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=4, ensure_ascii=False)
    print(f"\n💾 Saved full report to final_output_{timestamp}.json")