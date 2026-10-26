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

dates = sorted({d for s in flow.values() for d in s})
today = dates[-1]
last30 = dates[-30:]

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

# 主线监控
mainline = []
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
    mainline.append({
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
mainline.sort(key=lambda x: x["rank"] or 99)

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

cum300 = 0.0
etf_300 = []
for r in etf_rows:
    if r["code"] == "510300":
        cs = 0.0
        for i, d in enumerate(etf_dates):
            v = r["flows"][i]
            if v is not None:
                cs += v
            etf_300.append({"d": d, "v": v, "cum": round(cs, 1)})
        break

sent_path = os.path.join(OUT_DIR, "sentiment.json")
sentiment = None
if os.path.exists(sent_path):
    with open(sent_path, encoding="utf-8") as f:
        sentiment = json.load(f)

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
    "faded": faded,
    "etf": etfs,
    "etfSeries": {"dates": etf_dates, "rows": etf_rows, "total": etf_total, "hs300": etf_300},
    "sentiment": sentiment,
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
