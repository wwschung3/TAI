#!/usr/bin/env python3
"""
generate_tree.py

此腳本可作為 CrewAI 專案中「產生目錄結構」的工具。

主要用法：
- 命令列模式：`python generate_tree.py --root /path/to/project`
- 程式介面：`get_structure(root: str, is_follow_gitignore: bool = True, force_regenerate: bool = True, is_write_result: bool = True) -> dict`

新參數說明：
- force_regenerate (bool, default True):
    - True: 重新掃描目錄。
    - False: 若 `<root>/project_structure.json` 已存在，直接讀取並回傳該檔案內容（避免重新掃描）。
- is_write_result (bool, default True):
    - True: 在成功產生樹狀結構後，將結果寫入 `<root>/project_structure.json`（覆寫）。
    - False: 不寫入任何檔案；僅回傳計算結果（若同時使用 `force_regenerate=False`，仍會嘗試讀取現有檔案以作為快取來源）。

使用方式（CrewAI）：
    from generate_tree import get_structure
    # 重新產生並覆寫 JSON
    structure_dict = get_structure("/path/to/project", force_regenerate=True)
    # 或者若想重用已存在的快取檔案：
    structure_dict = get_structure("/path/to/project", force_regenerate=False)

此函式在成功產生樹狀結構後，會在目錄下寫入 `project_structure.json`（UTF-8、pretty JSON），
寫檔失敗僅會列印警告不會拋出例外。
"""

import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Union, Set

# -----------------------------
# 1. 參數解析
# -----------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a JSON representation of a directory tree."
    )
    parser.add_argument(
        "-r",
        "--root",
        type=str,
        help="Root directory to scan (required if you want to run the script)",
    )
    # 如果沒有任何參數，顯示說明並退出
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    return parser.parse_args()

# -----------------------------
# 2. 目錄遞迴
# -----------------------------
def walk_dir(
    path: Path,
    ignore: set[str] = None,
) -> List[Dict[str, Union[str, List]]]:
    """
    Recursively walk a directory and build a list of dicts.

    Each dict contains:
        - path: full path relative to the root
        - type: 'dir' or 'file'
        - extension: (only for files)
        - children: (only for dirs)
    """
    ignore = ignore or {"__pycache__", ".DS_Store", ".git"}
    items = []

    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name in ignore:
            continue

        rel_path = child.relative_to(root_path).as_posix()

        if child.is_dir():
            items.append(
                {
                    "path": rel_path,
                    "type": "dir",
                    "children": walk_dir(child, ignore),
                }
            )
        else:
            # 忽略 .pyc 檔案
            if child.suffix == ".pyc":
                continue

            items.append(
                {
                    "path": rel_path,
                    "type": "file",
                    "extension": child.suffix,
                }
            )

    return items

# ----------------------------------------------------------------------
# 3. 對外公開的函式（供 CrewAI 呼叫）
# ----------------------------------------------------------------------
def get_structure(root: str, is_follow_gitignore: bool = True, force_regenerate: bool = True, is_write_result: bool = True) -> Dict:
    """
    產生 `root` 目錄的樹狀結構（回傳 dict），支援依照 .gitignore 自動忽略檔案/資料夾。

    Args:
        root (str): 要掃描的根目錄路徑（絕對或相對皆可）。
        is_follow_gitignore (bool, optional): 是否讀取 `.gitignore` 檔案作為額外忽略條件。
                                              預設為 True。
        force_regenerate (bool, optional): 是否強制重新產生目錄結構（而非讀取快取檔案）。
                                           預設為 True。
        is_write_result (bool, optional): 是否將結果寫入 `<root>/project_structure.json`（預設 True）。

    Returns:
        Dict: 包含 `root` 鍵的完整結構字典，值為由 `walk_dir` 產生的樹狀資料。
    """
    # If force_regenerate is False and a previously generated JSON exists, return it
    # to avoid repeated filesystem scans.
    # -------------------------------------------------
    # 1️⃣ 讀取 .gitignore（若要求且檔案存在）
    # -------------------------------------------------
    ignore_set: Set[str] = set()
    if is_follow_gitignore:
        gitignore_path = Path(root).joinpath(".gitignore")
        if gitignore_path.is_file():
            try:
                with gitignore_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        # 去除前後空白、註解與空行
                        entry = line.strip()
                        if not entry or entry.startswith("#"):
                            continue
                        ignore_set.add(entry)
            except Exception as e:
                # 若讀取失敗，僅記錄錯誤（此範例不再拋出例外）
                print(f"⚠️  無法讀取 .gitignore：{e}")

    # -------------------------------------------------
    # 2️⃣ 呼叫內部實作 (walk_dir) 並把 ignore_set 傳入
    # -------------------------------------------------
    global root_path
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError(f"'{root}' is not a directory or does not exist.")

    out_path = root_path.joinpath("project_structure.json")
    if not force_regenerate and out_path.is_file():
        try:
            with out_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            # If loading fails, fall back to regenerating the structure
            print(f"⚠️  無法讀取現有 project_structure.json，將重新產生：{e}")

    # 合併預設的系統忽略項目（如 __pycache__、.git 等）
    default_ignore = {"__pycache__", ".DS_Store", ".git"}
    ignore_set.update(default_ignore)

    tree = {"root": walk_dir(root_path, ignore=ignore_set)}
    # Save a JSON copy of the structure in the target root for easy consumption
    # Write result to file only if requested.
    if is_write_result:
        try:
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(tree, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # Do not fail the function if writing the file fails; just print a warning
            print(f"⚠️  無法寫入 project_structure.json：{e}")
    return tree