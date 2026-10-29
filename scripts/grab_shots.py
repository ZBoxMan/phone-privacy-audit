#!/usr/bin/env python3
"""把 iPhone 上最近的截图拉到电脑，供报告核对用。

    .venv/bin/python scripts/grab_shots.py <输出目录> [--minutes 180] [--max 6]

只读。不许删除手机上任何文件，只是复制一份出来。
iPhone 的截图默认存成 PNG，相片是 JPG/HEIC，所以按后缀就能把截图挑出来。
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

SHOT_EXT = (".png",)
PHOTO_EXT = (".jpg", ".jpeg", ".heic")


def full(base, name):
    """afc 的 listdir 有时给全路径、有时只给名字，统一成绝对路径。"""
    if name.startswith("/"):
        return name
    return base.rstrip("/") + "/" + name.strip("/")


async def collect(lockdown, since, limit):
    from pymobiledevice3.services.afc import AfcService

    found = []
    async with AfcService(lockdown=lockdown) as afc:
        try:
            dirs = [full("/DCIM", d) for d in await afc.listdir("/DCIM")]
        except Exception:
            dirs = []
        for d in dirs:
            try:
                names = [full(d, n) for n in await afc.listdir(d)]
            except Exception:
                continue
            for path in names:
                low = path.lower()
                if not low.endswith(SHOT_EXT):
                    continue  # 只要 PNG；相片是 JPG/HEIC，跳过
                try:
                    st = await afc.stat(path)
                except Exception:
                    continue
                mtime = st.get("st_mtime")
                if not isinstance(mtime, datetime):
                    continue
                # afc 的时间带时区，去掉后按本地时间比
                naive = mtime.replace(tzinfo=None)
                if since and naive < since:
                    continue
                found.append((naive, path, st.get("st_size", 0)))

        found.sort(reverse=True)
        found = found[:limit]

        out = []
        for mtime, path, size in found:
            try:
                data = await afc.get_file_contents(path)
            except Exception:
                continue
            out.append({"path": path, "mtime": mtime, "size": size, "data": data})
    return out


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {}
    for i, a in enumerate(sys.argv):
        if a.startswith("--") and i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
            opts[a[2:]] = sys.argv[i + 1]

    out_dir = Path(args[0] if args else "./shots").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    minutes = int(opts.get("minutes", 180))
    limit = int(opts.get("max", 6))

    try:
        from pymobiledevice3.lockdown import create_using_usbmux
    except ImportError:
        print("ERROR: 缺少 pymobiledevice3，请用 skill 目录下的 venv 运行", file=sys.stderr)
        return 2

    try:
        lockdown = await create_using_usbmux(autopair=True)
    except Exception as e:
        print(f"ERROR: 连不上 iPhone —— {str(e).splitlines()[0][:100]}", file=sys.stderr)
        print("请确认数据线连着、手机解锁了、屏幕点了「信任」。", file=sys.stderr)
        return 3

    since = datetime.now() - timedelta(minutes=minutes)
    shots = await collect(lockdown, since, limit)

    if not shots:
        print(f"最近 {minutes} 分钟里没找到新截图。")
        print("在手机上截完图，再跑一次这个脚本就行。")
        return 0

    manifest = []
    for i, s in enumerate(shots, 1):
        name = f"{i}_{Path(s['path']).name}"
        (out_dir / name).write_bytes(s["data"])
        manifest.append({
            "file": name,
            "from": s["path"],
            "taken": s["mtime"].strftime("%Y-%m-%d %H:%M"),
            "kb": round(s["size"] / 1024),
        })

    import json
    (out_dir / "shots.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"拉到 {len(shots)} 张截图 → {out_dir}")
    for m in manifest:
        print(f"  {m['file']}  {m['taken']}  {m['kb']} KB")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
