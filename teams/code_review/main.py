# -*- coding: utf-8 -*-
"""
code_review_crew.py
示範如何在 Python 3.12 + crewai 環境下使用 ChatOllama + CrewAI。
"""

import os

# --------------------------------------------------------------
# 1️⃣ 載入核心套件
# --------------------------------------------------------------
from crewai import Agent, Task, Crew, LLM
from github import Github, Auth
from crewai.tools import tool
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

# --------------------------------------------------------------
# 2️⃣ 環境變數（可自行調整）
# --------------------------------------------------------------

load_dotenv()
os.environ["OPENAI_API_KEY"] = ""          # 不需要 OpenAI 金鑰

GITHUB_REPO_URL = os.getenv("GITHUB_REPO_URL")

## get the PR number from user input
PR_NUMBER   = input("Enter PR_NUMBER (e.g. 1234): ").strip()

# --------------------------------------------------------------
# 3️⃣ 建立本地 LLM（Ollama）
# --------------------------------------------------------------

print("Building LLM...")

reasoning_llm = LLM(
    #model="ollama/nemotron-3-nano:30b",
    model="ollama/devstral-small-2:24b",
    base_url="http://localhost:11434",
    temperature=0.1,
    timeout=1200,
)

local_qwen_coder = LLM(
    model="ollama/hhao/qwen2.5-coder-tools:14b",
    base_url="http://localhost:11434",
    temperature=0.1,
    config={
        "stop": ["\nObservation:", "\nFinal Answer:"],
        "num_ctx": 32768,
        "num_predict": 8192, # 確保能輸出完整的長代碼
        "request_timeout": 300
    }
)

# --------------------------------------------------------------
# 4️⃣ 初始化工具（這裡只保留最常用的兩個）
# --------------------------------------------------------------

print("Init custom tool...")

# from crewai_tools import SerperDevTool, GithubSearchTool

# search_tool      = SerperDevTool()
# github_search_tool = GithubSearchTool(
#     github_repo=os.getenv("GITHUB_REPO_URL"),
#     gh_token=os.getenv("GITHUB_TOKEN"),
#     content_types=["code", "pr"],
#     open_api_key="",
#     config=dict(
#         llm=dict(
#             provider="ollama",
#             config=dict(
#                 model="nemotron-3-nano:30b",
#                 base_url="http://localhost:11434",
#                 temperature=0.1,
#             )
#         ),
#         embedder=dict(
#             provider="ollama",
#             config=dict(
#                 model="nomic-embed-text",
#                 base_url="http://localhost:11434",
#             ),
#         ),
#     )
# )

# Custom Tool to get ACTUAL PR Content
@tool("fetch_pr_content")
def fetch_pr_content(pr_number: str) -> str:
    """Fetches the actual diff (code changes) and description of a GitHub PR."""
    try:
        pr_number = int(pr_number)
        auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
        g = Github(auth=auth)
        repo = g.get_repo(os.getenv("GITHUB_REPO_NAME"))
        pr = repo.get_pull(int(pr_number))
    

        # Get the diff (this is what the AI actually needs to review)
        diffs = []
        for file in pr.get_files():
            diffs.append(f"File: {file.filename}\nDiff:\n{file.patch}\n")

    except Exception as e:
        print(f"Error fetching PR content: {e}")
        return f"Error fetching PR content: {e}"
    return f"PR Title: {pr.title}\nDescription: {pr.body}\n\nChanges:\n" + "\n".join(diffs)

# --------------------------------------------------------------
# 5️⃣ 定義 Agent
# --------------------------------------------------------------

print("Setting up agents...")

data_fetcher = Agent(
    role="GitHub Data Collector",
    goal="Retrieve the full diff and description for PR #{PR_NUMBER}. Ensure the raw original diff result is output to the Final Answer without any analysis or summarisation.",
    backstory=(
        "You are a precise assistant that pulls raw data from GitHub APIs. "
        "If the result is normal, output the PR title, body, and the raw diff as the Final Answer. "
        "Do not modify the diff text. If an error occurs, output the error message."
        "Must not do any analysis or summarisation."
    ),
    tools=[fetch_pr_content],
    llm=local_qwen_coder,
    verbose=True,
    allow_delegation=False
)
data_fetcher.tools[0].result_as_answer = True

# token_analyzer = Agent(
#     role="Context Size Analyst",
#     goal="Calculate the required 'num_ctx' and 'num_predict' based on the size of the fetched diff.",
#     backstory=(
#         "You are an expert in LLM optimization. You analyze the character count and complexity "
#         "of code diffs to recommend the necessary context window (num_ctx) for a full review."
#     ),
#     llm=local_qwen_coder,
#     verbose=True
# )

code_reviewer = Agent(
    role="Senior Code Reviewer",
    goal="Review the supplied PR diff and produce a markdown report in Traditional Chinese.",
    backstory=(
        "You are an expert in PHP 8 and Magento 2. "
        "You review code changes for a git pull request (PR) for other developers. You do not write code; you find faults in others' code."
        "Provide a concise summary, list security issues, suggest refactorings, "
        "and identify missing documentation for new major classes or major functions."
        "除代碼內容入專有名詞外，你**必須且只能**使用『繁體中文』(Traditional Chinese)"
    ),
    llm=reasoning_llm,
    verbose=True,
    max_iter=5,             # Limit loops to prevent infinite thinking
)

# --------------------------------------------------------------
# 6️⃣ 定義 Task
# --------------------------------------------------------------
fetch_task = Task(
    description=f"Fetch all code changes and the description for PR #{PR_NUMBER} in the repo {GITHUB_REPO_URL}.",
    expected_output="The full text of the PR including all file diffs. Add the text to the output and Final Answer.",
    agent=data_fetcher
)

# token_count_task = Task(
#     description=(
#         "Analyze the text provided by the Data Collector. "
#         "1. Count the total characters in the diff.\n"
#         "2. Estimate the number of tokens (Char count / 4).\n"
#         "3. Recommend a 'num_ctx' (Context Window) which should be 2x the estimated tokens.\n"
#         "4. Estimate 'num_predict' based on the complexity of changes."
#     ),
#     expected_output="A brief summary including: Total Chars, Estimated Tokens, Recommended num_ctx, and Recommended num_predict.",
#     agent=token_analyzer,
#     context=[fetch_task]
# )

review_task = Task(
    description=(
        "You are now acting as the Senior Code Reviewer. "
        "Review the provided PR diff and write a report in Traditional Chinese (繁體中文). "
        "DO NOT explain the feature as if you wrote it. Your job is to CRITIQUE it. "
        "The report MUST include these sections:\n"
        "1. **安全性問題 (Security Issues)**: Identify vulnerabilities (SQLi, XSS, CSRF, etc.) or state 'None found'.\n"
        "2. **性能問題 (Performance Issues)**: Identify performance problems (N+1 queries, inefficient loops, heavy CPU/memeory/DB usage, etc.)'.\n"
        "3. **重構建議 (Refactoring Suggestions)**: Improvements for readability, PHP 8 standards, or Magento 2 patterns, poor naming of variables/functions/classes or missing exception handling.\n"
        "4. **缺失文件 (Missing Documentation)**: List new classes/methods missing DocBlocks or README updates.\n\n"
        "If there are no suggestions for a section, explicitly state '無' (None) for that section.\n\n"
        "If the diff is very long, focus on the logic-heavy files (PHP, JS) first."
        "If the provide content does not contain a normal code diff, report and abort tha task immidiately."
    ),
    expected_output="A structured Code Review report in Markdown format in Traditional Chinese (繁體中文) with the 5 required sections.",
    agent=code_reviewer,
)

# --------------------------------------------------------------
# 7️⃣ 建立 Crew
# --------------------------------------------------------------

crew = Crew(
    agents=[data_fetcher, code_reviewer],
    tasks=[fetch_task, review_task],
    process="sequential",
    verbose=True
)

# --------------------------------------------------------------
# 8️⃣ 執行
# --------------------------------------------------------------
if __name__ == "__main__":
    # 必須提供一個 dict，即使是空的也要有
    result = crew.kickoff(inputs={})
    print(result)
