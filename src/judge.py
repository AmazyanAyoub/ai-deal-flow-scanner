import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.schemas import NormalizedProject, JudgeOutput

class JudgeAgent:
    def __init__(self):
        # 1. Setup (Same as before)
        if os.getenv("GROQ_API_KEY"):
            self.llm = ChatGroq(
                model="llama-3.3-70b-versatile", 
                temperature=0,
                model_kwargs={"response_format": {"type": "json_object"}}
            )
        else:
            raise ValueError("❌ GROQ_API_KEY missing.")

        self.parser = PydanticOutputParser(pydantic_object=JudgeOutput)

        # 2. Prompt (Same as before)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are a strict AI Venture Capitalist writing for a top-tier Ukrainian tech channel. 
            
            ### SCORING CRITERIA (0-10)
            1. NOVELTY: Is this a new approach? (0=Wrapper, 10=Groundbreaking)
            2. MARKET LEVERAGE: Is the market huge? (0=Toy, 10=Global Infra)
            3. MOAT POTENTIAL: Is it hard to copy? (0=Script, 10=Deep Tech)
            4. EXECUTION SIGNAL: Is the engineering elite? (Docker, Tests, Docs)
            5. TIME TO MARKET: Is it ready now?

            ### TASKS
            1. Classify.
            2. Score.
            3. Draft Post (Russian).
            
            Format instructions: {format_instructions}
            """),
            ("human", """
            Analyze: {title}
            Desc: {description}
            URL: {url}
            
            Metrics: Stars {stars_total}, Velocity ~{stars_24h}/day, Age {age_days}d
            Signals: Docker {has_docker}, CI {has_ci}, Score {prod_score}
            
            Content: {raw_text}
            
            {format_instructions}
            """)
        ])

        self.chain = self.prompt | self.llm | self.parser

    def evaluate(self, project: NormalizedProject) -> JudgeOutput:
        # We keep ONE print just to know it started
        print(f"⚖️  VC Judging {project.title}...") 
        
        try:
            result = self.chain.invoke({
                "title": project.title,
                "description": project.description or "",
                "url": str(project.url),
                "stars_total": project.metrics.stars_total,
                "stars_24h": project.metrics.stars_24h,
                "age_days": project.metrics.age_days,
                "has_docker": project.signals.has_docker,
                "has_ci": project.signals.has_ci,
                "prod_score": project.signals.production_signals,
                "raw_text": project.raw_text[:4000], 
                "format_instructions": self.parser.get_format_instructions()
            })
            
            # Map Category back to project (Useful for DB)
            project.signals.category_guess = result.category_guess
            project.signals.category_confidence = result.category_confidence
            
            return result
            
        except Exception as e:
            print(f"❌ Error evaluating {project.title}: {e}")
            return None