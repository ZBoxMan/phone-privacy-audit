#!/usr/bin/env python3
"""把 audit.json 注入模板，生成自包含的 HTML 体检报告。"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "report.template.html"


def main():
    if len(sys.argv) < 2:
        print("用法: build_report.py <采集目录> [输出文件]", file=sys.stderr)
        return 2

    out_dir = Path(sys.argv[1]).resolve()
    audit_path = out_dir / "audit.json"
    if not audit_path.exists():
        print(f"ERROR: {audit_path} 不存在，请先运行 analyze.py", file=sys.stderr)
        return 2

    data = json.loads(audit_path.read_text(encoding="utf-8"))
    html = TEMPLATE.read_text(encoding="utf-8")

    # 数据里任何 "<" 都转成 \u003c：JSON 和 JS 都认，</script> 和 <!-- 就截不断脚本
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("<", "\\u003c")
    html = html.replace("__DATA__", payload)

    target = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else out_dir / "report.html"
    target.write_text(html, encoding="utf-8")
    print(f"报告已生成: {target}")
    print(f"体积: {len(html.encode('utf-8')) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
