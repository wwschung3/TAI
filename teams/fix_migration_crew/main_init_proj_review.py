import os
import sys
from dotenv import load_dotenv
import json

from crewai import Agent, Task, Crew, LLM, Process
from crewai.tools import tool
from langchain_ollama import ChatOllama
from crewai_tools import FileReadTool, FileWriterTool, DirectoryReadTool
from pathlib import Path

# --------------------------------------------------------------
# 環境變數（可自行調整）
# --------------------------------------------------------------
load_dotenv()
os.environ["OPENAI_API_KEY"] = ""          # 不需要 OpenAI 金鑰

# 把父目錄 (my_project) 加入 PYTHONPATH，讓 Python 能找到 tools/
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))
TOOLS_PATH = PROJECT_ROOT / "tools"
sys.path.append(str(TOOLS_PATH))

from generate_tree import get_structure

# 1. removed

# 2. DEFINE THE LOCAL LLM
# 
reasoning_llm = LLM(
    model="ollama/nemotron-3-nano:30b",
    base_url="http://localhost:11434",
    temperature=0.1,
    config={
        "request_timeout": 300,
        "stop": ["\nObservation:", "\nFinal Answer:"],
    }
)

# 3. INITIALIZE TOOLS
# These allow the AI to see your files and write new ones.
read_tool = FileReadTool()
write_tool = FileWriterTool()
dir_tool = DirectoryReadTool()

# -----------------------------
# CUSTOM TOOLS (grouped)
# -----------------------------
@tool("get_structure")
def get_structure_tool(root: str) -> str:
    """Tool wrapper around generate_tree.get_structure.

    The agent should call this tool with the target path (string). Returns
    a JSON string of the structure or an error JSON on failure.
    """
    # Require an explicit project path. If the caller passes None or '.' return
    # an instructional error so the agent (or user) knows to use
    # `inputs['project_path']`.
    if not root or root in (".", "./"):
        return json.dumps(
            {
                "error": (
                    "get_structure tool requires an explicit project path. "
                    "Call it with the project's absolute path (e.g. inputs['project_path'])"
                )
            },
            ensure_ascii=False,
        )

    try:
        structure = get_structure(root)
        return json.dumps(structure, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

# allow tool result as final answer
get_structure_tool.result_as_answer = True

# 4. DEFINE AGENTS


project_analyst = Agent(
    role="Project Structure Analyst",
    goal="根據專案結構提供清晰的理解摘要，協助團隊快速掌握模組分布。",
    backstory=(
        "You are an expert at analyzing project structures. "
        "You excel at generating a concise summary that captures the essence of the project layout. "
    ),
    # This agent should use the precomputed structure provided in
    # `inputs['project_structure']`. Do NOT call external tools for the initial
    # analysis — read the `project_structure` input and produce a concise summary.
    tools=[],
    verbose=True,
    allow_delegation=False,
    # Disable function-calling/tool-invocation behavior so the agent returns a
    # plain-text summary instead of emitting a tool-like JSON payload.
    function_calling_llm=None,
    # 以下示例使用 OpenAI 的 GPT-4；若您使用其他模型，請自行調整
    llm=reasoning_llm,
)


# 5. DEFINE TASKS
# Task 1: Scoping
review_project_structure_task = Task(
    description=(
        "請根據以下提供的資訊進行分析：\n\n"
        "【專案結構】:\n{project_structure}\n\n"
        "【README 內容】（如有）:\n{project_readme}\n\n"
        "基於上述資料撰寫一段 100 行以內的簡短摘要，說明 與主要模組分布。報告結構盡可能包含：\n"
        "- Agent 對專案的理解\n"
        "- 專案概述\n"
        "- 專案主要功能及使用場景\n"
        "- 技術棧與架構\n"
        "- 技術風險評估\n"
        "嚴格要求：最終輸出必須是純文字（Plain text）答案，且不得以 JSON、程式碼區塊或工具呼叫（如 view_file / file_path JSON）作為最終回覆。\n"
        "最終輸出應為兩個版本：繁體中文及英文版本。\n"
    ),
    expected_output="格式化且結構清晰的純文字分析報告。",
    agent=project_analyst
)


crew = Crew(
    agents=[project_analyst],
    tasks=[review_project_structure_task],
    process=Process.sequential,
    manager_llm=None, 
    # process=Process.hierarchical,  # 開啟層級模式
    # manager_llm=local_qwen_coder,      # 必須指定經理的大腦 
    verbose=True, # True = print through process to terminal
    share_crew=False, # False = do not connect with external, stay on local
    cache=False
)


# 7. START THE PROCESS
if __name__ == "__main__":
    # Ensure an argument is provided
    if len(sys.argv) < 2:
        print("\n[!] Error: Missing project path.")
        print("Usage: python fix_migration_crew.py <path_to_project>")
        print("Example: python fix_migration_crew.py /Users/xxx/www/lpm/fixapp\n")
        sys.exit(1)

    # Convert the required argument to an absolute path
    target_path = os.path.abspath(sys.argv[1])
    
    # Optional: Verify the path exists before starting the crew
    if not os.path.exists(target_path):
        print(f"\n[!] Error: The path '{target_path}' does not exist.\n")
        sys.exit(1)
    
    print(f"### Target Project: {target_path} ###")
    
    inputs = {
        'project_path': target_path,
        'output_path': os.path.join(os.getcwd(), 'migrated_project')
    }
    # --- Pre-compute the directory structure and attach to inputs so the
    # project_analyst agent can analyze it deterministically. The agent may
    # still call the `get_structure` tool if it prefers.
    try:
        structure = get_structure(target_path, is_follow_gitignore=True)
        inputs['project_structure'] = structure
        print(inputs['project_structure'])
        # also include a JSON string version for tools or agents that expect text
        inputs['project_structure_json'] = json.dumps(structure, ensure_ascii=False)
        print("[i] Attached project_structure to inputs for the agent to analyze.")
    except Exception as e:
        inputs['project_structure_error'] = str(e)
        print(f"[!] Warning: could not precompute project structure: {e}")

    # Try to find a README file in the project root and attach its text to inputs
    readme_candidates = [
        "README.md",
        "README.rst",
        "README.txt",
        "README",
        "readme.md",
        "readme.txt",
        "Readme.md",
    ]
    inputs['project_readme'] = None
    for name in readme_candidates:
        p = Path(target_path).joinpath(name)
        if p.is_file():
            try:
                with p.open("r", encoding="utf-8") as f:
                    inputs['project_readme'] = f.read()
                inputs['project_readme_path'] = str(p)
                print(f"[i] Attached README from {p}")
                break
            except Exception as e:
                print(f"[!] Could not read README {p}: {e}")

    result = crew.kickoff(inputs=inputs)