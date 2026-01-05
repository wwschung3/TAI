"""
teams/requirement_interview/main.py

Major purpose:
    - Run an interactive requirements-interview Crew that uses a question/response
        tool to extract a full project specification from a user and produce a
        Markdown specification plus a step-by-step build plan.

Usage:
    - From the repository root run:
            python3 teams/requirement_interview/main.py
    - Ensure the `common_tools/askUserQuestions` tool is available on the
        PYTHONPATH and an Ollama-compatible local model is running if using LLMs.
"""

import sys
import os

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from pathlib import Path

# --------------------------------------------------------------
# 環境變數（可自行調整）
# --------------------------------------------------------------
load_dotenv()
os.environ["OPENAI_API_KEY"] = ""          # 不需要 OpenAI 金鑰


# 引入共用工具
PROJECT_ROOT = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_ROOT.parent.parent
sys.path.append(str(ROOT_DIR))
COMMON_TOOLS_PATH = ROOT_DIR / "common_tools"
sys.path.append(str(COMMON_TOOLS_PATH))

# 引入專案專屬工具
PROJECT_TOOLS_PATH = PROJECT_ROOT / "tools"
sys.path.append(str(PROJECT_TOOLS_PATH))

# 引入訪談工具
try:
    from askUserQuestions import AskUserQuestions
except ImportError as e:
    print(f"Error: Could not find tools folder. Ensure your structure is correct. {e}")
    sys.exit(1)

interview_tool = AskUserQuestions()

try:
    from AdaptiveMarkdownWriter import AdaptiveMarkdownWriter
except ImportError as e:
    print(f"Error: Could not find AdaptiveMarkdownWriter tool. Ensure your structure is correct. {e}")
    sys.exit(1)

save_output_file_tool = AdaptiveMarkdownWriter()

# Define the LLM(s)
reasoning_llm = LLM(
    model="ollama/devstral-small-2:24b",
    base_url="http://localhost:11434",
    temperature=0.1,
    config={
        "request_timeout": 300,
        "stop": ["\nObservation:", "\nFinal Answer:"],
    }
)

# 2. Define the Architect Agent
architect_agent = Agent(
    role='Senior Solution Architect and Product Manager',
    goal='Conduct a deep-dive interview to extract complete project specifications.',
    backstory=(
        "You are an expert at uncovering hidden technical risks and UX edge cases. "
        "You use the Project_Requirements_Interview_Tool to talk to the user. "
        "You don't stop until you have enough info to build a full Markdown Spec. "
        "After the interview, you analyze the project topic, create a fitting filename, and save the spec using the save_output_file_tool. "
    ),
    llm=reasoning_llm,
    tools=[interview_tool, save_output_file_tool],
    verbose=True,
    allow_delegation=False,
    max_iter=15 # Increased to allow for multiple interview rounds
)

# 3. Define the Task
interview_task = Task(
    description=(
        "Start the interview by asking about the project vision and core technical challenges. "
        "Continue the dialogue using the tool until you have sufficient details. "
        "Final Output must be: "
        "1. a comprehensive Markdown Specification Document, and "
        "2. a step-by-step plan with exact commands to build the project from scratch. "
        "3. Determine a unique, descriptive filename based on the project topic. "
        "4. Use the save_output_file_tool to save the final document physically."
    ),
    expected_output="A complete, professional Software Specification Document in Markdown format, along with a step by step plan provide exact command to build the project that is saved to a file with custom file name and a confirmation message of the absolute path.",
    agent=architect_agent
)

# 4. Start the Crew
project_crew = Crew(
    agents=[architect_agent],
    tasks=[interview_task]
)

result = project_crew.kickoff()
print(result)