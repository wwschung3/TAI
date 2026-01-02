import os
import sys
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OPENAI_API_KEY"] = "NA"

from crewai import Agent, Task, Crew, Process
from langchain_community.chat_models import ChatOllama
from crewai_tools import FileReadTool, FileWriterTool, DirectoryReadTool

# 1. removed

# 2. DEFINE THE LOCAL LLM

# 
local_qwen_coder = ChatOllama(
    model="ollama_chat/hhao/qwen2.5-coder-tools:14b",
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

# 
local_gpt_20b = ChatOllama(
    model="ollama_chat/gpt-oss:20b",
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

# 4. DEFINE AGENTS
# Agent 1: The Analyst who finds the "old" stuff.
analyst = Agent(
    role='Legacy Java & FIX Analyst',
    goal='Identify deprecated QuickFIX/J dependencies and APIs in {project_path}',
    backstory=(
        "You are an expert in java and financial exchange protocol systems. Your job is to "
        "find code that won't work in Java 17 or QuickFIX/J 2.3.1+. "
        "When using tools, you ALWAYS provide the input in a valid JSON dictionary format. "
    ),
    tools=[dir_tool, read_tool],
    llm=local_qwen_coder,
    verbose=True,
    allow_delegation=False,
    max_iter=5,
    function_calling_llm=local_qwen_coder,
    respect_context_window=True 
)

# Agent 2: The Developer who writes the "new" stuff.
developer = Agent(
    role='Java Refactoring Specialist',
    goal='Rewrite Java files into modern, clean, and compiling code.',
    backstory=(
        "You take migration reports and turn them into actual code. "
        "When using tools, you ALWAYS provide the input in a valid JSON dictionary format. "
        "After using the FileWriterTool, you always verify that the tool returned a success message. "
        "If the write tool fails, you try again with a smaller code block."
        "You are a master of Java 17 features (Records, Switch expressions) "
        "and you are very good at QuickFIX/J 2.x API."
    ),
    tools=[read_tool, write_tool],
    llm=local_qwen_coder,
    verbose=True,
    allow_delegation=False,
    max_iter=3
)

# Agent 3: The QA / Verifier
qa_engineer = Agent(
    role='Java Quality Assurance Engineer',
    goal='Verify that all refactored files exist in {output_path} and contain valid code.',
    backstory=(
        "You are a strict code reviewer. You do not trust the developer's word. "
        "You physically check the 'migrated_project' folder using tools to ensure "
        "files are not empty and that the code actually uses QuickFIX/J 2.x APIs."
    ),
    tools=[dir_tool, read_tool], # It needs to see what was written
    llm=local_qwen_coder,
    verbose=True,
    allow_delegation=False # Allow it to ask the developer to fix it if it's wrong
)

# 5. DEFINE TASKS
# Task 1: Scoping
analysis_task = Task(
    description=(
        "Scan the directory at {project_path}. Identify the current QuickFIX/J version "
        "and list all MessageCracker or Application methods that need updating."
    ),
    #expected_output="A list of specific code blocks and dependencies that need upgrading.",
    expected_output="A plain text summary of the current project version and file names.",
    agent=analyst
)

# Task 2: Refactoring
migration_task = Task(
    description=(
        "Using the analyst's report, rewrite the old Java classes. "
        "Ensure all package imports are updated and new API methods are used. "
        "Write the updated code to a new folder named 'migrated_project'."
    ),
    expected_output="Fully refactored Java source files saved in the migrated_project folder.",
    agent=developer
)

verification_task = Task(
    description=(
        "1. Scan the 'migrated_project' folder.\n"
        "2. For every file the developer claimed to write, read the content.\n"
        "3. If a file is empty or missing, or if it still contains old 'MessageCracker' logic, "
        "instruct the developer to redo that specific file.\n"
        "4. Only finalize the process once you have confirmed the files exist and are correct."
    ),
    expected_output="A final audit report confirming all files are correctly migrated and saved.",
    agent=qa_engineer,
    context=[migration_task] # This links the QA task to the Developer's output
)

# 6. ASSEMBLE THE CREW
crew = Crew(
    agents=[analyst, developer, qa_engineer],
    tasks=[analysis_task, migration_task, verification_task],
    # process=Process.sequential,
    # manager_llm=None, 
    process=Process.hierarchical,  # 開啟層級模式
    manager_llm=local_qwen_coder,      # 必須指定經理的大腦 
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
    
    result = crew.kickoff(inputs=inputs)