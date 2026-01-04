import os
from crewai.tools import BaseTool

class AdaptiveMarkdownWriter(BaseTool):
    """
    Adaptive Markdown writer tool.

    Purpose:
      - Allow an AI agent to save arbitrary Markdown content to a file whose
        filename is decided by the agent.

    Usage:
      - The tool accepts either:
          1) Two arguments: (filename, content)
          2) A single JSON/dict-like string as the first argument with keys
             'filename' and 'content'.

    Behavior:
      - Sanitizes the filename (replaces spaces with underscores and drops
        any directory path, writing into the current working directory).
      - Ensures the filename ends with `.md`.
    """

    name: str = "adaptive_markdown_writer_tool"
    description: str = (
        "Adaptive tool to save Markdown content to a filename chosen by the AI agent. "
        "Accepts either (filename, content) or a single JSON/dict string with 'filename' and 'content' keys. "
        "The filename will be sanitized and forced to end with '.md'."
    )

    def _run(self, filename: str, content: str | None = None) -> str:
        # Support being passed a single JSON/dict-like string as the first arg
        if content is None:
            # try to parse filename as JSON or dict-like
            try:
                import json as _json

                if isinstance(filename, str):
                    parsed = _json.loads(filename)
                else:
                    parsed = filename

                fname = parsed.get("filename")
                content = parsed.get("content")
            except Exception:
                return "Error: expected either (filename, content) or a JSON string with 'filename' and 'content'."
        else:
            fname = filename

        if not fname or not isinstance(fname, str):
            return "Error: invalid filename provided."

        # Sanitize filename: remove path components and replace spaces
        safe_name = os.path.basename(fname).replace(" ", "_").lower()
        if not safe_name.endswith(".md"):
            safe_name += ".md"

        try:
            with open(safe_name, "w", encoding="utf-8") as f:
                f.write(content or "")
            return f"Successfully saved markdown to {safe_name}"
        except Exception as e:
            return f"Error saving file: {str(e)}"