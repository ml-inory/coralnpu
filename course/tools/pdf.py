#!/usr/bin/env python3
"""把课程 Markdown 渲染成 PDF（pandoc + weasyprint）。

每节课有两本册子：
  基础知识.pdf —— 先把理论讲清楚，附在线书籍/规范/文章链接
  作业说明.pdf —— 任务拆解、验收标准、调试方法、提交要求

用法：
  ./learn pdf L00        # 只渲染 L00
  ./learn pdf all        # 渲染所有已编写的课程
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)
ROOT = os.path.dirname(COURSE)

DOCS = [
    ("basics.md", "基础知识", "理论、术语与参考资料"),
    ("homework.md", "作业说明", "任务拆解、验收标准与调试方法"),
]

# 每节课的封面信息：目录名 -> (阶段号, 主标题, 副标题)
LESSON_META = {
    "P0_prep": ("P0", "预备课：零基础桥接", "补齐读懂 L00/L01 作业说明所需的前置知识"),
    "L00_setup": ("L00", "环境、工具链与仓库地图", "从零开始：把「写 RTL → 仿真 → 对拍」跑通一次"),
    "L01_scalar": ("L01", "RV32I 单周期核", "从零实现一颗能跑真实 C 程序的 RISC-V 核心"),
    "L02_lsu": ("L02", "访存子系统（LSU）", "把访存从核心里的几行逻辑变成带握手的状态机"),
    "L03a_pipeline": ("L03a", "流水线与冒险", "把单周期核改成 5 级流水线，并处理数据/控制/结构冒险"),
}


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def pandoc_html(md_path: str, title: str) -> str:
    """返回 (html 正文, html 目录)。"""
    template = os.path.join(COURSE, "style", "template.html")
    cmd = [
        "pandoc",
        md_path,
        "-f", "markdown+pipe_tables+fenced_code_blocks+tex_math_dollars",
        "-t", "html5",
        "--standalone",
        "--toc",
        "--toc-depth=2",
        "--template", template,
        "--metadata", f"title={title}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"pandoc 失败：\n{proc.stderr}")
    return proc.stdout


def inline_css(html: str) -> str:
    """把样式表内联进 HTML。

    之前模板里用的是 <link href="../../style/lesson.css">，而构建目录在
    lessons/<课>/.pdfbuild/ 下，相对路径实际解析到 course/lessons/style/...（不存在），
    于是 WeasyPrint 静默跳过样式表：图片没有 max-width 被裁掉、页面边距与字号全丢。
    内联之后不再依赖任何相对路径。
    """
    css_path = os.path.join(COURSE, "style", "lesson.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    return html.replace("<!--@@CSS@@-->", f"<style>\n{css}\n</style>")


def absolute_assets(html: str, md_dir: str) -> str:
    """把 Markdown 里的相对图片路径改成绝对路径，避免受构建目录位置影响。"""

    def repl(match: re.Match) -> str:
        attr, url = match.group(1), match.group(2)
        if url.startswith(("http://", "https://", "data:", "file://", "#")):
            return match.group(0)
        path = os.path.normpath(os.path.join(md_dir, url))
        if not os.path.exists(path):
            print(f"    ⚠️  插图不存在：{url}（按 {md_dir} 解析）")
            return match.group(0)
        return f'{attr}="file://{path}"'

    return re.sub(r'(src|href)="([^"]+)"', repl, html)


def render_doc(lesson_dir: str, lesson: str, md_name: str, doc_title: str, subtitle: str) -> str:
    code, main_title, lesson_sub = LESSON_META[lesson]
    src = os.path.join(lesson_dir, md_name)
    if not os.path.exists(src):
        raise SystemExit(f"缺少 {src}")

    build_dir = os.path.join(lesson_dir, ".pdfbuild")
    os.makedirs(build_dir, exist_ok=True)
    out_dir = os.path.join(lesson_dir, "pdf")
    os.makedirs(out_dir, exist_ok=True)

    html = pandoc_html(src, f"{code} {doc_title}")
    html = absolute_assets(inline_css(html), os.path.dirname(os.path.abspath(src)))
    # 填模板里的字段
    cover_image = ""
    cover_path = os.path.join(lesson_dir, "diagrams", "cover.png")
    if os.path.exists(cover_path):
        cover_image = '<div class="cover-art"><img src="../diagrams/cover.png" alt=""></div>'
    html = (
        html.replace("@@STAGE@@", code)
        .replace("@@MAIN_TITLE@@", f"{code} · {main_title}")
        .replace("@@SUBTITLE@@", f"{doc_title} —— {subtitle}")
        .replace("@@COVER_IMAGE@@", cover_image)
        .replace("@@DATE@@", datetime.date.today().isoformat())
    )
    html_path = os.path.join(build_dir, md_name.replace(".md", ".html"))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    pdf_path = os.path.join(out_dir, f"{doc_title}.pdf")
    proc = subprocess.run(["weasyprint", "-e", "utf-8", html_path, pdf_path],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"weasyprint 失败：\n{proc.stderr[-2000:]}")
    return pdf_path


def render_lesson(lesson: str) -> list[str]:
    lesson_dir = os.path.join(COURSE, "lessons", lesson)
    if not os.path.isdir(lesson_dir):
        raise SystemExit(f"没有这个课程目录：{lesson}")
    out = []
    for md_name, doc_title, subtitle in DOCS:
        path = render_doc(lesson_dir, lesson, md_name, doc_title, subtitle)
        size = os.path.getsize(path) / 1024
        print(f"  ✅ {os.path.relpath(path, ROOT)}  （{size:.0f} KB）")
        out.append(path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="渲染课程 PDF")
    ap.add_argument("target", nargs="?", default="all", help="L00 / L01 / all / lessons 目录名")
    args = ap.parse_args()

    missing = [c for c in ("pandoc", "weasyprint") if not have(c)]
    if missing:
        print(f"缺少 {'、'.join(missing)}，先运行 ./learn doctor --install")
        return 2

    if args.target == "all":
        lessons = [d for d in sorted(os.listdir(os.path.join(COURSE, "lessons")))
                   if os.path.isdir(os.path.join(COURSE, "lessons", d))]
    else:
        key = args.target.upper()
        lesson = next((d for d in LESSON_META if d.upper().startswith(key)), None)
        if not lesson:
            lesson = args.target
        lessons = [lesson]

    print("渲染课程 PDF：")
    count = 0
    for lesson in lessons:
        if not os.path.exists(os.path.join(COURSE, "lessons", lesson, "basics.md")):
            continue
        print(f"[{lesson}]")
        count += len(render_lesson(lesson))
    print(f"完成，共 {count} 个 PDF。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
