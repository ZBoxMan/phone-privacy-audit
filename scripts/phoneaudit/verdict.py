"""一句话结论。人工核对出的问题优先于机器判的；数据太薄时不许说「没问题」。"""


def make_verdict(findings, manual, platform="android", summary=None, completeness=None) -> dict:
    verdict = _verdict(findings, manual, platform, summary)
    return _thin_data_override(verdict, summary or {}, completeness or {})


def _thin_data_override(verdict: dict, summary: dict, completeness: dict) -> dict:
    """数据不充分时不能说「没发现问题」——那会把读不到说成没问题。"""
    ok_n = completeness.get("ok", 0)
    bad_n = completeness.get("failed", 0)
    thin = []
    if summary.get("total_apps", 0) == 0:
        thin.append("一个软件都没读到")
    if ok_n == 0:
        thin.append("所有检查项都没跑通")
    elif bad_n > ok_n:
        thin.append(f"{bad_n} 项没跑通、只有 {ok_n} 项成功")
    if not thin or verdict["tone"] == "bad":
        return verdict
    return {
        "tone": "warn",
        "headline": "这次能看到的太少，说明不了问题",
        "detail": f"{'，'.join(thin)}。下面的结论只覆盖读到的那部分，"
                  "没读到的部分不等于没问题。按「这次没查到的地方」里的说明手工核对一遍更靠谱。",
    }


def _verdict(findings, manual, platform, summary) -> dict:
    high = [f for f in findings if f["level"] == "high"]
    check = [f for f in findings if f["level"] == "check"]
    watch = [f for f in findings if f["level"] == "watch"]
    manual_bad = [m for m in manual if m.get("answer") == "yes"]
    summary = summary or {}

    if high:
        return {"tone": "bad",
                "headline": f"有 {len(high)} 个软件，先看看",
                "detail": "下面每一条都写了它哪儿不对、你该干什么。弄完可以再查一次。"}
    if manual_bad:
        # 人工核对查出来的东西优先级高于应用层面，标题里直接点名，别让人往下找
        names = "、".join(m.get("title") or m.get("id", "") for m in manual_bad[:3])
        more = f" 等 {len(manual_bad)} 项" if len(manual_bad) > 3 else ""
        return {"tone": "bad",
                "headline": f"核对出 {len(manual_bad)} 个问题",
                "detail": f"{names}{more}。这些是你亲眼确认的，比机器猜的靠谱。"
                          "往下翻「你自己看到的那几项」看怎么处理。"
                          + (f"另外 {len(check)} 个软件可以顺带看看。" if check else "")}
    if summary.get("limited"):
        return {"tone": "warn",
                "headline": "机器能看的只有软件清单",
                "detail": "这台手机不开放权限和安装来源的查询，所以这里判不出谁有问题。"
                          "往下翻「谁能动你的手机」，不认识的软件自己在设置里搜一下。"}
    if check:
        return {"tone": "warn",
                "headline": f"{len(check)} 个软件，有空看看",
                "detail": "都不是病毒，就是有些地方说不通。不着急。"}
    if watch:
        # iPhone 上「没有非商店安装」是真正的结论，要单独说出来，
        # 不然一律写「没看出什么问题」，等于把好消息也说没了。
        if platform == "ios" and not summary.get("side_loaded"):
            return {"tone": "ok",
                    "headline": "没有商店之外的软件",
                    "detail": f"iPhone 上能绕开苹果进来的坏东西，这次一个都没有。"
                              f"剩下 {len(watch)} 个是权限要得多，不算问题，"
                              "想收一收的往下看「它想打听你多少事」。"}
        return {"tone": "ok",
                "headline": "没看出什么问题",
                "detail": f"有 {len(watch)} 个软件有点小情况，都算不上问题。"}
    return {"tone": "ok",
            "headline": "没看出什么问题",
            "detail": "这次看到的范围里，没有要你处理的。"}
