#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
在桌面创建/修复「知识库」快捷方式。

为什么要这个脚本：
  1. 图标必须放在**知识库目录之外**。E:\\Knowledge 这棵树的 ACL 被 DSH 沙箱改造过
     （含 S-1-4-… 能力 SID），Windows 从快捷方式提取图标用的是沙箱化的提取进程，
     读不到库内的图标文件 → 只会显示默认白纸。放到 %LOCALAPPDATA% 就正常。
  2. 这样以后换了机器、或快捷方式被删掉，双击一下就能重建。

用法：
    python tools\\install_shortcut.py            # 创建/覆盖桌面快捷方式
    python tools\\install_shortcut.py --name KB  # 换个名字
"""
from __future__ import annotations

import argparse
import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_SRC = ROOT / "tools" / "kb.ico"
ICON_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Knowledge"
ICON_DST = ICON_DIR / "kb.ico"
GUI = ROOT / "tools" / "gui.pyw"


def pick_powershell() -> str:
    for name in ("pwsh", "powershell"):
        exe = shutil.which(name)
        if exe:
            return exe
    sys.exit("找不到 pwsh / powershell，无法创建快捷方式。")


def ensure_icon() -> Path:
    if not ICON_SRC.exists():
        print("图标不存在，先生成：python tools\\make_icon.py")
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_icon.py")], check=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ICON_SRC, ICON_DST)
    return ICON_DST


def make_shortcut(name: str, icon: Path) -> str:
    """用 PowerShell 的 WScript.Shell 建 .lnk；快捷方式名用 Base64 传，避免编码问题。"""
    b64 = base64.b64encode(name.encode("utf-8")).decode("ascii")
    target = shutil.which("pythonw") or sys.executable
    ps = (
        "$n=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}'));"
        "$p=[IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),$n+'.lnk');"
        "$ws=New-Object -ComObject WScript.Shell;"
        "$l=$ws.CreateShortcut($p);"
        "$l.TargetPath='{target}';"
        "$l.Arguments='\"{gui}\"';"
        "$l.WorkingDirectory='{wd}';"
        "$l.IconLocation='{icon},0';"
        "$l.Description='Knowledge console';"
        "$l.Save(); Write-Output $p"
    ).format(b64=b64, target=target, gui=GUI, wd=ROOT, icon=icon)
    out = subprocess.run([pick_powershell(), "-NoProfile", "-NonInteractive", "-Command", ps],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        sys.exit(f"创建失败：{out.stderr.strip() or out.stdout.strip()}")
    return out.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="创建桌面快捷方式")
    ap.add_argument("--name", default="知识库", help="快捷方式名字（默认：知识库）")
    args = ap.parse_args()

    if not GUI.exists():
        sys.exit(f"找不到 {GUI}")
    icon = ensure_icon()
    lnk = make_shortcut(args.name, icon)
    print(f"图标已安装到：{icon}")
    print(f"快捷方式已创建：{lnk}")
    print("如果桌面图标没立刻变，按 F5 刷新一下桌面。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
