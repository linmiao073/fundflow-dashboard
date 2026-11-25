# -*- coding: utf-8 -*-
"""把资金流数据导出为前端可直接加载的 data.js（window.DATA）"""
import json, os, datetime

DATA_DIR = r"C:\Users\game-netease\AppData\Roaming\LobsterAI\openclaw\state\workspace-stockexpert\data"
OUT_DIR = r"C:\Users\game-netease\lobsterai\project\fundflow"

BLACK = {"电子","通信","计算机","医药生物","食品饮料","电力设备","机械设备","汽车","房地产","银行",
         "非银金融","国防军工","基础化工","有色金属","钢铁","煤炭","石油石化","公用事业","建筑材料",
         "家用电器","商贸零售","交通运输","传媒","纺织服饰","农林牧渔","环保","社会服务","建筑装饰",
         "美容护理","轻工制造","综合","电力"}

def load(name):
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

flow = load("flow_history.json") or {}
raw = load("daily_flow_raw.json") or {}
etf_daily = load("etf_daily.json") or {}
etf_hist = load("etf_history.json") or {}
watch = load("mainline_watch.json") or {}

sent_path = os.path.join(OUT_DIR, "sentiment.json")
sentiment = None
if os.path.exists(sent_path):
    with open(sent_path, encoding="utf-8") as f:
        sentiment = json.load(f)

# 同花顺题材（真实主线概念 + 玄学 + 跌停板块），由 scripts/collect_ths.py 生成
ths = load("ths_sentiment.json") or {}
themes = ths.get("themes") or []
board_theme = ths.get("boardTheme") or {}
dt_boards = ths.get("dtBoards") or []
ths_date = ths.get("date") or ""
ths_stale = False

# 情绪展示口径：炸板率取整、最高连板取整
if sentiment:
    if sentiment.get("zbr") is not None:
        sentiment["zbr"] = int(round(sentiment["zbr"]))
    if sentiment.get("maxLbc") is not None:
        sentiment["maxLbc"] = int(sentiment["maxLbc"])
    for sg in (sentiment.get("signals") or []):
        if sg.get("k") == "炸板率" and sg.get("v") is not None:
            v = sg["v"] * (100 if sg["v"] <= 1 else 1)
            sg["v"] = int(round(v))
    sentiment["dtBoards"] = dt_boards


dates = sorted({d for s in flow.values() for d in s})
today = dates[-1]
last30 = dates[-30:]

# 题材数据必须与当日行情同日，否则不复用（避免拿旧题材当今日主线）
if ths_date and ths_date != today.replace("-", ""):
    ths_stale = True
    themes, board_theme, dt_boards = [], {}, []

# 一级行业合计（市场总口径）
level1 = [n for n in flow if n in BLACK and n != "电力"]
market = []
for d in last30:
    v = sum(flow[n].get(d, 0) for n in level1)
    market.append({"d": d, "v": round(v / 1e8, 1)})

# 今日 pct / 换手 / 市值（来自今日快照 meta）
meta = {}
for row in (raw.get("meta") or []):
    meta[row[0]] = {"pct": row[1], "turnover": row[2], "rate": row[3], "mktcap": row[4]}

uni = [n for n in flow if n not in BLACK]
today_vals = sorted(((n, flow[n].get(today, 0)) for n in uni), key=lambda x: -x[1])
top12 = today_vals[:12]
bot12 = today_vals[-12:][::-1]

def pack(items):
    out = []
    for name, v in items:
        m = meta.get(name, {})
        out.append({
            "name": name,
            "v": round(v / 1e8, 2),
            "pct": m.get("pct"),
            "rate": m.get("rate"),
            "cap": round((m.get("mktcap") or 0) / 1e8, 0) if m.get("mktcap") else None,
        })
    return out

# 12日累计
last12 = dates[-12:]
cum = []
for n in uni:
    s = sum(flow[n].get(d, 0) for d in last12)
    posd = sum(1 for d in last12 if flow[n].get(d, 0) > 0)
    cum.append((n, s, posd))
cum_up = sorted(cum, key=lambda x: -x[1])[:12]
cum_dn = sorted(cum, key=lambda x: x[1])[:12]

def pack_cum(items):
    return [{"name": n, "v": round(s / 1e8, 1), "days": p} for n, s, p in items]

# 资金面候选（旧口径，行业板块组；保留作趋势页次要参考）
flow_candidates = []
for c in (watch.get("candidates") or []):
    boards = [b for b in c["boards"] if b in flow]
    if not boards:
        continue
    series = []
    for d in dates[-10:]:
        v = sum(flow[b].get(d, 0) for b in boards)
        series.append({"d": d, "v": round(v / 1e8, 1)})
    # 取板块组里最强的板块做代表指标
    rep = max(boards, key=lambda b: sum(flow[b].get(d, 0) for d in dates[-5:]))
    s = flow[rep]
    d5 = sum(s.get(d, 0) for d in dates[-5:]) / 1e8
    d3 = sum(s.get(d, 0) for d in dates[-3:]) / 1e8
    dv = s.get(today, 0) / 1e8
    streak = 0
    for d in reversed(dates):
        if s.get(d, 0) > 0:
            streak += 1
        else:
            break
    flow_candidates.append({
        "rank": c.get("rank"),
        "line": c.get("line"),
        "rep": rep,
        "boards": boards,
        "d5": round(d5, 1),
        "d3": round(d3, 1),
        "today": round(dv, 1),
        "streak": streak,
        "pct": (meta.get(rep) or {}).get("pct"),
        "evidence": c.get("evidence"),
        "upgrade": c.get("upgrade_trigger"),
        "invalidate": c.get("invalidate"),
        "note": c.get("note"),
        "series": series,
    })
flow_candidates.sort(key=lambda x: x["rank"] or 99)


def board_to_flow(name):
    """东财涨停池的 hybk 是截断名（汽车零部），映射到完整板块名"""
    if name in flow:
        return name
    for k in flow:
        if k.startswith(name) or name.startswith(k):
            return k
    return None


# 题材关键词 -> 行业板块（资金面口径补充，避免只用涨停股所在行业）
THEME_BOARDS = {
    "机器人": ["机器人", "自动化设备", "工控设备", "其他自动化设备", "电机", "汽车零部件"],
    "芯片": ["半导体", "数字芯片设计", "模拟芯片设计", "集成电路设计", "半导体设备", "分立器件"],
    "人工智能": ["软件开发", "IT服务", "计算机设备", "通信设备"],
    "华为": ["消费电子", "光学光电子", "通信设备"],
    "汽车": ["汽车零部件", "底盘与发动机系统", "其他汽车零部件", "汽车电子电气系统"],
    "消费": ["白酒", "食品饮料", "商业百货", "家电行业"],
}


# 主线（真实题材口径）：同花顺涨停板块 × 东财行业资金
high_lb = {h.get("code"): h for h in ((sentiment or {}).get("high") or [])}
xu_codes = {x.get("code") for x in (ths.get("xuanxue") or [])}
auto_notes = {}
for c in (watch.get("candidates") or []):
    key = (c.get("line") or "").split(" / ")[0]
    auto_notes[key] = c

mainline = []
accepted = []
sub_themes = []
for t in themes[:8]:
    if (t.get("zt") or 0) < 5 and (t.get("lb") or 0) < 4:
        continue
    tset = set(t.get("codes") or [])
    parent = None
    for a in accepted:
        if tset and len(tset & a["codes"]) / len(tset) >= 0.7:
            parent = a["theme"]
            break
    if parent:
        sub_themes.append({"theme": t["name"], "parent": parent, "zt": t.get("zt"), "lb": t.get("lb"), "high": t.get("high")})
        continue
    names = [b for b, v in board_theme.items() if v.get("theme") == t["name"]]
    for kw, bs in THEME_BOARDS.items():
        if kw in t["name"]:
            names = bs + names
            break
    seen = set()
    fboards = []
    for nm in names:
        fb = board_to_flow(nm)
        if fb and fb not in seen:
            seen.add(fb)
            fboards.append(fb)
    fboards = fboards[:5]
    boards = []
    for fb in fboards:
        hit = [k for k in board_theme if board_to_flow(k) == fb]
        boards.append(hit[0] if hit else fb)
    series = []
    if fboards:
        for d in dates[-10:]:
            v = sum(flow[b].get(d, 0) for b in fboards)
            series.append({"d": d, "v": round(v / 1e8, 1)})
    d5 = sum((p["v"] for p in series[-5:]), 0)
    d3 = sum((p["v"] for p in series[-3:]), 0)
    dv = series[-1]["v"] if series else 0
    reps = []
    for r in (t.get("reps") or [])[:4]:
        h = high_lb.get(r.get("code")) or {}
        reps.append({"code": r.get("code"), "name": r.get("name"), "lb": h.get("lbc"),
                     "board": h.get("board"), "reason": r.get("reason")})
    mt = None
    for k, c in auto_notes.items():
        if k and (k in t["name"] or t["name"][:2] in k):
            mt = c
            break
    cover = round(sum((board_theme[b].get("cover") or 0) for b in boards if b in board_theme) /
                  max(1, sum((board_theme[b].get("n") or 0) for b in boards if b in board_theme)), 2) if boards else 0
    xu_cnt = sum(1 for c in (t.get("codes") or []) if c in xu_codes)
    mainline.append({
        "rank": len(mainline) + 1,
        "theme": t["name"],
        "zt": t.get("zt"),
        "lb": t.get("lb"),
        "high": t.get("high"),
        "boards": boards,
        "cover": cover,
        "d5": round(d5, 1),
        "d3": round(d3, 1),
        "today": round(dv, 1),
        "reps": reps,
        "xuanxue": (xu_cnt / max(1, len(t.get("codes") or []))) >= 0.25,
        "evidence": (mt or {}).get("evidence") or (
            "涨停 %d 家 / 连板 %d 只 / 高度 %s；行业板块 %s 涨停股中 %d%% 属该题材" % (
                t.get("zt") or 0, t.get("lb") or 0, t.get("high") or "-",
                "/".join(boards[:3]) or "-", int(cover * 100))),
        "upgrade": (mt or {}).get("upgrade_trigger") or "题材内出现更高连板 + 板块单日≥20亿净流入",
        "invalidate": (mt or {}).get("invalidate") or "高位断板无接力，涨停家数连续 2 日缩水 30% 以上",
        "note": (mt or {}).get("note"),
        "series": series,
    })
    accepted.append({"theme": t["name"], "codes": tset})

# 已退潮
faded = []
for line, desc in ((watch.get("already_faded") or {}).items()):
    if line == "conclusion":
        continue
    faded.append({"line": line, "desc": desc})

# ETF（今日）
etfs = []
for e in (etf_daily.get("etfs") or []):
    code = e.get("code")
    h = etf_hist.get(code, {}).get("days", {})
    days = sorted(h.keys())
    cum5 = sum((h[d].get("flow") or 0) for d in days[-5:]) / 1e8
    amt_hist = [x for x in (e.get("amtHist") or []) if x.get("amt")]
    avg = sum(x["amt"] for x in amt_hist[-5:]) / len(amt_hist[-5:]) if amt_hist else None
    vr = round(e["amount"] / avg, 2) if (avg and e.get("amount")) else None
    etfs.append({
        "code": code,
        "name": e.get("name"),
        "pct": e.get("pct"),
        "amount": round((e.get("amount") or 0) / 1e8, 1),
        "flow": round((e.get("flow") or 0) / 1e8, 2),
        "cum5": round(cum5, 2),
        "vr": vr,
        "isIndex": code in ("000688", "399006", "000001"),
    })

# 轮动：相邻 TOP10 重合度
rot = []
prev = None
for d in dates[-16:]:
    cur = set(n for n, _ in sorted(((n, flow[n].get(d, 0)) for n in uni), key=lambda x: -x[1])[:10])
    if prev is not None:
        rot.append({"d": d, "j": round(len(prev & cur) / len(prev | cur), 2)})
    prev = cur

# 个股 TOP（今日）
stocks = []
for s in ((raw.get("stocks") or {}).get("marketTop") or [])[:10]:
    try:
        stocks.append({"code": s[0], "name": s[1], "price": s[2], "pct": s[3], "v": round((s[5] or 0) / 1e8, 1)})
    except Exception:
        pass

# ETF 逐日序列（每支 + 合计）
wf = load("etf_watch.json") or {}
tracked = [(i["secid"].split(".")[1], i["name"]) for i in (wf.get("items") or []) if not i.get("index")]
etf_dates = set()
for code, _ in tracked:
    etf_dates.update(etf_hist.get(code, {}).get("days", {}).keys())
etf_dates = sorted(etf_dates)[-20:]
etf_rows = []
for code, nm in tracked:
    days = etf_hist.get(code, {}).get("days", {})
    flows, amts = [], []
    for d in etf_dates:
        rec = days.get(d) or {}
        flows.append(round((rec.get("flow") or 0) / 1e8, 2) if d in days else None)
        amts.append(round((rec.get("amount") or 0) / 1e8, 1) if d in days else None)
    etf_rows.append({"code": code, "name": (days and nm) or nm, "flows": flows, "amounts": amts})

etf_total = []
cum = 0.0
for i, d in enumerate(etf_dates):
    s = sum((r["flows"][i] or 0) for r in etf_rows if r["flows"][i] is not None)
    cum += s
    etf_total.append({"d": d, "v": round(s, 1), "cum": round(cum, 1)})

# 沪深300ETF 合计（大图口径，只含沪深300家族；扩展时在此追加 510310 易方达 / 159919 嘉实 / 510330 华夏）
HS300_CODES = [("510300", "沪深300ETF(华泰柏瑞)")]
hs300_rows = []
cum300 = 0.0
for d in etf_dates:
    vals = []
    for code, _nm in HS300_CODES:
        rec = (etf_hist.get(code) or {}).get("days", {}).get(d) or {}
        if rec.get("flow") is not None:
            vals.append(rec["flow"] / 1e8)
    v = round(sum(vals), 2) if vals else None
    if v is not None:
        cum300 += v
    hs300_rows.append({"d": d, "v": v, "cum": round(cum300, 1)})

# ETF 净申购（申赎口径，由 scripts/build_etf_subflow.py 生成）
sub_path = os.path.join(OUT_DIR, "data", "sub_flow.json")
sub = None
if os.path.exists(sub_path):
    with open(sub_path, encoding="utf-8") as f:
        sub = json.load(f)

payload = {
    "generatedAt": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
    "date": today,
    "market": market,
    "today": {
        "total": market[-1]["v"] if market else 0,
        "top": pack(top12),
        "bottom": pack(bot12),
        "inCount": sum(1 for _, v in today_vals if v > 0),
        "outCount": sum(1 for _, v in today_vals if v < 0),
        "detailSum": round(sum(v for _, v in today_vals) / 1e8, 1),
    },
    "cum": {"days": 12, "up": pack_cum(cum_up), "down": pack_cum(cum_dn)},
    "mainline": mainline,
    "subThemes": sub_themes,
    "flowCandidates": flow_candidates,
    "themes": [{"rank": t.get("rank"), "name": t["name"], "zt": t.get("zt"), "lb": t.get("lb"),
                "high": t.get("high"),
                "xuanxue": (sum(1 for c in (t.get("codes") or []) if c in xu_codes) / max(1, len(t.get("codes") or []))) >= 0.25,
                "reps": (t.get("reps") or [])[:4]} for t in themes[:8]],
    "xuanxue": [{"code": x.get("code"), "name": x.get("name"), "themes": x.get("themes"),
                 "text": x.get("text")} for x in (ths.get("xuanxue") or [])],
    "dtBoards": dt_boards,
    "themesDate": ths_date,
    "themesStale": ths_stale,
    "stockConcepts": {k: v for k, v in (ths.get("stockConcepts") or {}).items()
                      if k in ({h.get("code") for h in ((sentiment or {}).get("high") or [])} |
                               {h.get("code") for h in ((sentiment or {}).get("high") or [])})},
    "faded": faded,
    "etf": etfs,
    "etfSeries": {"dates": etf_dates, "rows": etf_rows, "total": etf_total, "hs300": hs300_rows,
                  "hs300Codes": [c for c, _ in HS300_CODES], "hs300Names": [n for _, n in HS300_CODES]},
    "sentiment": sentiment,
    "sub": sub,
    "rotation": rot,
    "stocks": stocks,
    "regime": (watch.get("regime") or {}),
}

os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, "data.js"), "w", encoding="utf-8") as f:
    f.write("window.DATA = ")
    f.write(json.dumps(payload, ensure_ascii=False, indent=1))
    f.write(";\n")

with open(os.path.join(OUT_DIR, "data.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=1)

print("date=", today, "market points=", len(market), "mainline=", len(mainline), "etf=", len(etfs))
print("bytes=", os.path.getsize(os.path.join(OUT_DIR, "data.js")))
