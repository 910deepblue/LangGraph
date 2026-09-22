r"""批量运行 steps/ 下所有脚本，把结果汇总成一个报告。

为什么要这个脚本：本机 PowerShell 工具环境下无法捕获 Python 子进程的 stdout
（输出被吞），所以让 Python 自己用 subprocess 跑完再写文件。

用法：
    .\.venv\Scripts\python.exe run_all.py
输出：
    _verify_report.txt
"""

import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "_verify_report.txt"

# 需要跑的都列在这（s5/s6 需要 API key，本机没配时会走降级路径）
STEPS = [
    "check_env",
    "s1_minimal",
    "s2_state",
    "s3_branch",
    "s4_loop",
    "s5_llm",
    "s6_tools",
    "s7_persist",
]


def run_script(name: str) -> str:
    """把脚本当独立进程跑，捕获 stdout / stderr / 退出码。"""
    # check_env 在根目录，其余在 steps/
    script = ROOT / f"{name}.py" if name == "check_env" else ROOT / "steps" / f"{name}.py"
    if not script.exists():
        return f"########## {name} ##########\n!! 脚本不存在: {script}\n"

    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            timeout=120,
        )
        return "\n".join([
            f"########## {name} ##########",
            f"exit_code = {proc.returncode}   ({script.name})",
            "--- stdout ---",
            proc.stdout.rstrip() or "(空)",
            "--- stderr ---",
            proc.stderr.rstrip() or "(空)",
            "",
        ])
    except subprocess.TimeoutExpired:
        return f"########## {name} ##########\n!! 超时（120s）\n"
    except Exception:
        return f"########## {name} ##########\n!! 异常:\n{traceback.format_exc()}\n"


def main() -> None:
    parts = []
    for name in STEPS:
        parts.append(run_script(name))

    REPORT.write_text("\n".join(parts), encoding="utf-8")

    # 本机环境下 stderr 反而能透出来，用它提示
    print(f"报告已写入: {REPORT}", file=sys.stderr)
    print(f"共跑了 {len(STEPS)} 个脚本", file=sys.stderr)


if __name__ == "__main__":
    main()
