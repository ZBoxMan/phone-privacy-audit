"""手机体检的分析引擎。只读采集结果进来，audit.json 出去；不碰设备。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANUAL_ITEMS = ROOT / "references" / "manual-items.json"
