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

local_navdia = LLM(
    model="ollama/nemotron-3-nano:30b",
    base_url="http://localhost:11434",
    temperature=0.1,
    timeout=300,
)

local_qwen_coder = LLM(
    model="ollama/hhao/qwen2.5-coder-tools:14b",
    base_url="http://localhost:11434",
    temperature=0.1,
    config={
        "request_timeout": 300,
        "stop": ["\nObservation:", "\nFinal Answer:"],
        "num_ctx": 32768,
        "num_predict": 8192, # 確保能輸出完整的長代碼
        "request_timeout": 600
    }
)

# --------------------------------------------------------------
# 4️⃣ 初始化工具（這裡只保留最常用的兩個）
# --------------------------------------------------------------
from crewai_tools import SerperDevTool, GithubSearchTool

search_tool      = SerperDevTool()
github_search_tool = GithubSearchTool(
    github_repo=os.getenv("GITHUB_REPO_URL"),
    gh_token=os.getenv("GITHUB_TOKEN"),
    content_types=["code", "pr"],
    open_api_key="",
    config=dict(
        llm=dict(
            provider="ollama",
            config=dict(
                model="nemotron-3-nano:30b",
                base_url="http://localhost:11434",
                temperature=0.1,
            )
        ),
        embedder=dict(
            provider="ollama",
            config=dict(
                model="nomic-embed-text",
                base_url="http://localhost:11434",
            ),
        ),
    )
)

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
data_fetcher = Agent(
    role="GitHub Data Collector",
    goal="Retrieve all code changes for the specified PR.",
    backstory="You are a precise assistant that pulls raw data from GitHub APIs.",
    tools=[fetch_pr_content],
    llm=local_qwen_coder,
    verbose=True,
    allow_delegation=False
)

code_reviewer = Agent(
    role="Senior Software Engineer",
    goal="Access the internet for best practices and review GitHub code for quality and bugs.",
    backstory="Expert in php8 and magento2. You provide constructive feedback.",
    llm=local_navdia,
    verbose=True,
    max_iter=5,             # Limit loops to prevent infinite thinking
)

# --------------------------------------------------------------
# 6️⃣ 定義 Task
# --------------------------------------------------------------
fetch_task = Task(
    description=f"Fetch all code changes and the description for PR #{PR_NUMBER} in the repo {GITHUB_REPO_URL}.",
    expected_output="The full text of the PR including all file diffs. Add the text to the output and Final Answer",
    agent=data_fetcher
)

review_task = Task(
    description=(
        f"1. Use the GitHub tool to search for the specific changes in PR #{PR_NUMBER} in the repo {GITHUB_REPO_URL}. \n"
        f"2. Read the code diffs carefully.\n"
        f"3. Provide a report including: Summary, Security Issues, and Refactoring Suggestions in zh-tw.\n"
    ),
    expected_output="A structured markdown report reviewing the code in the PR.",
    agent=code_reviewer,
)

# --------------------------------------------------------------
# 7️⃣ 建立 Crew
# --------------------------------------------------------------
crew = Crew(
    agents=[data_fetcher, code_reviewer],
    tasks=[fetch_task, review_task],
    process="sequential",
    verbose=True, # True = print through process to terminal
)

# --------------------------------------------------------------
# 8️⃣ 執行
# --------------------------------------------------------------
if __name__ == "__main__":
    # 必須提供一個 dict，即使是空的也要有
    result = crew.kickoff(inputs={})
    print(result)