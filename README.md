## Overview;
This is an attempt of using CrewAI to cooridinate multiple local AI models for a complex task (migrating an multi-years-old quickfixj project to fit the latest update).

## To Run:
```
source .venv/bin/activate
python fix_migration_crew.py {project_directory_path}
```

## Project Status:
The script will fail as local AI is weak and it also failed to response with the correct CrewAI expected format.

Turns out its an issue with gpt-oss:20b, swtiching to hhao/qwen2.5-coder-tools:14b, successfully ran on small directory.

