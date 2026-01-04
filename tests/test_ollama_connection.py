from crewai import LLM

# 修正後的 LLM 定義
local_llm = LLM(
    model="ollama/gpt-oss:20b",        # 必須包含 ollama/ 前綴
    base_url="http://localhost:11434/v1", # 建議加上 /v1
    api_key="ollama"                   # LiteLLM 有時需要一個非空的 dummy key
)

print("LLM Initialized Successfully")