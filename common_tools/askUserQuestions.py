from crewai.tools import BaseTool
from pydantic import Field

class AskUserQuestions(BaseTool):
    """A tool to conduct in-depth interviews for gathering project specifications."""

    name: str = "ask_user_questions_Tool"
    description: str = (
        "Useful for when you need to gather project specifications from the user. "
        "The tool will prompt the user with your questions. Follow the Role Persona: "
        "Act as a Senior Solution Architect & PM. Ask 2-3 deep questions about tech stacks, "
        "concurrency, trade-offs, and UX edge cases. If responses are contradictory, "
        "challenge them."
    )

    def _run(self, question: str) -> str:
        # This function pauses the agent and waits for your typing in the terminal
        print(f"\n\n[Architect/PM Agent is asking]:\n{question}")
        user_response = input("\n[Your Answer]: ")
        return user_response