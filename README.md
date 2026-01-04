## Overview;
This is an attempt of using CrewAI to cooridinate multiple local AI models for a complex task (migrating an multi-years-old quickfixj project to fit the latest update).

## Installation:
```
python3.12 -m venv venv
source venv/bin/activate
python3.12 -m pip install -r installation/requirements.txt
```

## To Run:
```
source venv/bin/activate
python3.12 teams/<team>/main.py
```

## Project Status:
The script will fail as local AI is weak and it also failed to response with the correct CrewAI expected format.

Turns out its an issue with gpt-oss:20b, swtiching to hhao/qwen2.5-coder-tools:14b, successfully ran on small directory.

