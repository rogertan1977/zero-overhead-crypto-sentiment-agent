#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zero-Overhead Crypto Sentiment Agent (100% Adaptive / Zero Hardcoded KOLs)
适用环境：无 GPU / 老旧 PC (i7-4770) / 树莓派 / 低内存 VPS (<50MB 增量内存)
核心原则：绝不硬编码任何特定 KOL 名称或频道，纯基于语义密度、二次媒体穿透与互动率过滤。
依赖安装：pip install pytrends scrapetube requests
"""

import gc
import html
import json
import logging
import os
import random
import re
import sys
import time
import tracemalloc
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import requests
import scrapetube
from pytrends.request import TrendReq

# ==============================================================================
# 1. 全局配置区 (支持环境变量或直接在此处修改)
# ==============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_HERE")

# Google Trends 监控地区: "" 代表全球, "US" 代表美国
TRENDS_GEO = os.getenv("TRENDS_GEO", "")
TRENDS_TIMEFRAME = "now 7-d"

# Web 端 4 大核心搜索意图词库 (每批 <= 5 个词以防归一化压缩失真)
INTENT_GROUPS: Dict[str, List[str]] = {
    "1_散户买入意向": [
        "buy bitcoin",
        "how to buy bitcoin",
        "coinbase",
        "binance",
        "bitget",
    ],
    "2_极端恐慌与洗盘": [
        "is bitcoin dead",
        "bitcoin crash",
        "crypto liquidation",
        "bitcoin bear market",
    ],
    "3_宏观机构叙事": [
        "spot bitcoin etf",
        "microstrategy bitcoin",
        "btc etf inflow",
        "fed rate cut",
    ],
    "4_山寨与垂直投机": [
        "hyperliquid",
        "polymarket",
        "next 100x crypto",
        "altcoin season",
    ],
}

# 可随时追加的临时热点监测词
EXTRA_KEYWORDS: List[str] = [
    "crypto",
    "anthropic ipo",
]

# 【规则 1：纯语义图谱与专用索引词库】（严禁硬编码任何个人频道或名称）
YOUTUBE_SEMANTIC_QUERIES: Dict[str, List[str]] = {
    "EN": [
        "bitcoin macro metrics OR liquidation OR MVRV OR SOPR",
        "spot bitcoin etf outflow OR realized price OR on-chain analysis",
    ],
    "CN": [
        "比特币 链上指标 共振 仓位 破位",
        "比特币 ETF 资金流出 爆仓 流动性 宏观",
    ],
}

# 高信息密度专业术语词典（用于计算语义密度、过滤纯标题党泛娱乐大号）
HIGH_DENSITY_TERMS = [
    "mvrv", "sopr", "realized price", "etf", "inflow", "outflow", "liquidation",
    "open interest", "funding rate", "macro", "fed", "cpi", "yield", "dominance",
    "mnav", "msci", "on-chain", "whale", "support", "resistance", "gamma",
    "链上", "指标", "共振", "仓位", "破位", "爆仓", "清算", "净流出", "净流入",
    "巨鲸", "已实现价格", "宏观", "利率", "流动性", "市占率", "结构", "支撑",
]

# 确定性情绪词典（免 LLM 轻量 NLP）
PANIC_KEYWORDS = [
    "crash", "dead", "zero", "collapse", "dump", "bears", "bear market",
    "danger", "warning", "stuck", "dilemma", "capitulat", "liquidat",
    "wipeout", "fear", "panic", "selloff", "worse", "breakdown",
    "暴跌", "崩盘", "归零", "危险", "血洗", "破位", "腰斩", "惨赔",
    "亏损", "割肉", "恐慌", "熊市", "大跌", "插针", "抛压", "失血",
]

BULL_FOMO_KEYWORDS = [
    "100x", "moon", "ath", "skyrocket", "explode", "buy now", "bull run",
    "parabolic", "breakout", "reversal", "surge", "rally", "accumulate",
    "暴涨", "百倍", "牛市", "冲刺", "反转", "抄底", "起飞", "爆发", "吸筹",
]

# 共识主题聚类映射表（用于二次媒体 & 社区热帖高频共识提炼）
CONSENSUS_TOPICS: Dict[str, List[str]] = {
    "ETF 资金流向": ["etf", "inflow", "outflow", "ibit", "blackrock", "资金流出", "净流入"],
    "衍生品爆仓与去杠杆": ["liquidat", "wipeout", "leverage", "open interest", "爆仓", "清算", "多空"],
    "宏观利率与流动性": ["fed", "rate", "cpi", "yield", "treasury", "ipo", "加息", "降息", "流动性", "美债"],
    "机构持仓与矿工成本": ["microstrategy", "strategy", "mstr", "msci", "miner", "cost", "机构", "矿工", "抛压"],
    "技术破位与抄底博弈": ["support", "200-week", "bottom", "dip", "whale", "支撑", "破位", "抄底", "巨鲸"],
}

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("AdaptiveSentimentAgent")


# ==============================================================================
# 2. 轻量解析与评分工具
# ==============================================================================
def _safe_text(obj: Any) -> str:
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, dict):
        if "simpleText" in obj:
            return str(obj["simpleText"]).strip()
        if "runs" in obj and isinstance(obj["runs"], list):
            return "".join(str(r.get("text", "")) for r in obj["runs"]).strip()
    return ""


def _parse_compact_number(raw: str) -> int:
    """将 '1.2K', '3.4M', '12,345 views', '1.5万' 转为整数。"""
    if not raw:
        return 0
    cleaned = raw.upper().replace(",", "").replace(" ", "")
    m = re.search(r"([\d.]+)\s*([KMB万亿]?)", cleaned)
    if not m:
        return 0
    num = float(m.group(1))
    unit = m.group(2)
    mult = {
        "": 1,
        "K": 1_000,
        "M": 1_000_000,
        "B": 1_000_000_000,
        "万": 10_000,
        "亿": 100_000_000,
    }.get(unit, 1)
    return int(num * mult)


def _parse_duration_sec(length_text: str) -> int:
    """解析 '12:34' 或 '1:02:03' 时长文本为秒数，用于过滤 <90s 的低信息密度 Shorts。"""
    if not length_text or ":" not in length_text:
        return 0
    parts = [p for p in length_text.strip().split(":") if p.isdigit()]
    try:
        vals = [int(p) for p in parts]
        if len(vals) == 2:
            return vals[0] * 60 + vals[1]
        if len(vals) == 3:
            return vals[0] * 3600 + vals[1] * 60 + vals[2]
    except Exception:
        pass
    return 0


def _score_text(text: str) -> Tuple[int, int, int]:
    """返回 (恐慌词命中数, 亢奋词命中数, 专业语义密度命中数)。"""
    low = text.lower()
    p_hits = sum(1 for kw in PANIC_KEYWORDS if kw in low)
    b_hits = sum(1 for kw in BULL_FOMO_KEYWORDS if kw in low)
    d_hits = sum(1 for kw in HIGH_DENSITY_TERMS if kw in low)
    return p_hits, b_hits, d_hits


# ==============================================================================
# 3. 市场行情与 Google Trends 4 大意图模块
# ==============================================================================
def fetch_market_snapshot(session: requests.Session) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {
        "btc_price": None,
        "btc_24h_pct": None,
        "btc_dominance": None,
        "fgi_now": None,
        "fgi_label": "Unknown",
        "fgi_7d_ago": None,
    }

    try:
        r = session.get("https://api.alternative.me/fng/?limit=7", timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        if data:
            snapshot["fgi_now"] = int(data[0]["value"])
            snapshot["fgi_label"] = data[0].get("value_classification", "")
            if len(data) >= 7:
                snapshot["fgi_7d_ago"] = int(data[-1]["value"])
    except Exception as exc:
        logger.warning("恐慌贪婪指数抓取失败: %s", exc)

    try:
        r = session.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=10,
        )
        r.raise_for_status()
        btc = r.json().get("bitcoin", {})
        snapshot["btc_price"] = btc.get("usd")
        snapshot["btc_24h_pct"] = btc.get("usd_24h_change")
    except Exception as exc:
        logger.warning("CoinGecko 价格接口失败 (%s)，切换 Coinbase 回退...", exc)
        try:
            r2 = session.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=10)
            r2.raise_for_status()
            snapshot["btc_price"] = float(r2.json()["data"]["amount"])
        except Exception as exc2:
            logger.warning("Coinbase 价格回退失败: %s", exc2)

    try:
        r = session.get("https://api.coingecko.com/api/v3/global", timeout=10)
        r.raise_for_status()
        snapshot["btc_dominance"] = (
            r.json().get("data", {}).get("market_cap_percentage", {}).get("btc")
        )
    except Exception as exc:
        logger.warning("BTC 市占率抓取失败: %s", exc)

    return snapshot


def fetch_google_trends() -> Dict[str, List[Dict[str, Any]]]:
    """抓取 Web 端 4 大核心意图与追加词过去 7 天趋势，立即销毁 DataFrame 释放内存。"""
    results: Dict[str, List[Dict[str, Any]]] = {}
    all_batches: List[Tuple[str, List[str]]] = list(INTENT_GROUPS.items())

    for i in range(0, len(EXTRA_KEYWORDS), 5):
        chunk = EXTRA_KEYWORDS[i : i + 5]
        if chunk:
            all_batches.append((f"5_追加热点监测_{i // 5 + 1}", chunk))

    try:
        pytrends = TrendReq(hl="en-US", tz=480, timeout=(8, 20))
    except Exception as exc:
        logger.error("TrendReq 初始化失败: %s", exc)
        return results

    for group_name, kw_list in all_batches:
        rows: List[Dict[str, Any]] = []
        ok = False
        for attempt in range(2):
            try:
                pytrends.build_payload(
                    kw_list, cat=0, timeframe=TRENDS_TIMEFRAME, geo=TRENDS_GEO
                )
                df = pytrends.interest_over_time()
                if df is not None and not df.empty:
                    if "isPartial" in df.columns:
                        df = df.drop(columns=["isPartial"])
                    for kw in kw_list:
                        if kw in df.columns:
                            series = df[kw].tolist()
                            latest = int(series[-1]) if series else 0
                            avg_val = round(sum(series) / max(len(series), 1), 1)
                            delta_pct = (
                                round(((latest - avg_val) / avg_val) * 100, 1)
                                if avg_val > 0
                                else 0.0
                            )
                            rows.append(
                                {
                                    "kw": kw,
                                    "latest": latest,
                                    "avg_7d": avg_val,
                                    "delta_pct": delta_pct,
                                }
                            )
                del df
                gc.collect()
                ok = True
                break
            except Exception as exc:
                logger.warning("Google Trends [%s] 第 %d 次受限: %s", group_name, attempt + 1, exc)
                time.sleep(random.uniform(4.0, 6.5))

        results[group_name] = rows
        if ok:
            time.sleep(random.uniform(2.5, 4.0))

    del pytrends
    gc.collect()
    return results


# ==============================================================================
# 4. 自适应 YouTube 抓取与互动率过滤模块 (零硬编码 KOL)
# ==============================================================================
def _probe_watch_engagement(
    session: requests.Session, video_id: str, fallback_views: int
) -> Tuple[int, int, int]:
    """
    轻量请求播放页 HTML 文本（不加载任何音视频与浏览器内核），
    用正则从 ytInitialData/ytInitialPlayerResponse 提取 (views, likes, comments)，
    提完即刻释放内存。
    """
    views, likes, comments = fallback_views, 0, 0
    try:
        resp = session.get(
            f"https://www.youtube.com/watch?v={video_id}&hl=en",
            timeout=8,
        )
        if resp.status_code != 200:
            return views, likes, comments
        text = resp.text
        del resp

        # 1) 提取精确播放量
        m_view = re.search(r'"viewCount"\s*:\s*"(\d+)"', text)
        if m_view:
            views = int(m_view.group(1))

        # 2) 多模式提取点赞数
        like_patterns = [
            r'"likeCount"\s*:\s*(\d+)',
            r'like this video along with ([\d,]+) other',
            r'"accessibilityText"\s*:\s*"([\d,]+)\s+likes?"',
            r'"factoidRenderer".*?"value"\s*:\s*\{"simpleText"\s*:\s*"([\d.,]+[KMB]?)"\}.*?"Likes"',
        ]
        for pat in like_patterns:
            m_like = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
            if m_like:
                likes = _parse_compact_number(m_like.group(1))
                if likes > 0:
                    break

        # 3) 多模式提取评论数
        comment_patterns = [
            r'"commentsEntryPointHeaderRenderer".*?"commentCount"\s*:\s*\{"simpleText"\s*:\s*"([\d.,]+[KMB]?)"',
            r'"commentsEntryPointHeaderRenderer".*?"content"\s*:\s*"([\d.,]+[KMB]?)"',
            r'"commentCount"\s*:\s*"(\d+)"',
        ]
        for pat in comment_patterns:
            m_comm = re.search(pat, text, flags=re.DOTALL)
            if m_comm:
                comments = _parse_compact_number(m_comm.group(1))
                if comments > 0:
                    break

        del text
        gc.collect()
    except Exception as exc:
        logger.debug("探测视频 %s 互动指标失败: %s", video_id, exc)

    return views, likes, comments


def fetch_adaptive_youtube(
    session: requests.Session, top_n_per_lang: int = 4
) -> Dict[str, List[Dict[str, Any]]]:
    """
    基于【规则 1 语义索引】与【规则 3 互动比过滤 (Comments+Likes)/Views】，
    全自动发现高信息密度分析视频，自动剔除泛娱乐大号与超短水视频。
    """
    adaptive_results: Dict[str, List[Dict[str, Any]]] = {"EN": [], "CN": []}

    for lang, queries in YOUTUBE_SEMANTIC_QUERIES.items():
        candidates: Dict[str, Dict[str, Any]] = {}

        for q in queries:
            try:
                gen = scrapetube.get_search(
                    query=q, limit=6, sleep=1.0, sort_by="upload_date"
                )
                for v in gen:
                    vid = v.get("videoId", "")
                    if not vid or vid in candidates:
                        continue
                    title = _safe_text(v.get("title"))
                    if not title:
                        continue

                    # 过滤 Shorts 或 <90 秒的短平快标题党（保留直播流 length=0）
                    dur_sec = _parse_duration_sec(_safe_text(v.get("lengthText")))
                    if 0 < dur_sec < 90:
                        continue

                    channel_name = _safe_text(v.get("ownerText")) or "Unknown Channel"
                    pub_time = _safe_text(v.get("publishedTimeText")) or "近期/直播"
                    view_raw = _safe_text(v.get("viewCountText")) or _safe_text(
                        v.get("shortViewCountText")
                    )
                    views_est = _parse_compact_number(view_raw)
                    snippet = _safe_text(v.get("detailedMetadataSnippets", [{}])[0].get("snippetText")) if isinstance(v.get("detailedMetadataSnippets"), list) and v.get("detailedMetadataSnippets") else ""

                    p_hits, b_hits, d_hits = _score_text(f"{title} {snippet}")
                    candidates[vid] = {
                        "video_id": vid,
                        "title": title,
                        "channel": channel_name,
                        "published": pub_time,
                        "views": views_est,
                        "panic_hits": p_hits,
                        "bull_hits": b_hits,
                        "density_hits": d_hits,
                        "url": f"https://youtu.be/{vid}",
                    }
            except Exception as exc:
                logger.warning("YouTube 语义检索 [%s] 异常: %s", q, exc)
            time.sleep(random.uniform(0.8, 1.4))

        # 先按语义密度初筛最多 6 个候选视频去轻量探测 (Comments + Likes) / Views
        pre_sorted = sorted(
            candidates.values(),
            key=lambda x: (x["density_hits"], x["views"]),
            reverse=True,
        )[:6]

        scored_list: List[Dict[str, Any]] = []
        for item in pre_sorted:
            views, likes, comments = _probe_watch_engagement(
                session, item["video_id"], item["views"]
            )
            item["views"] = views
            item["likes"] = likes
            item["comments"] = comments

            if views > 0 and (likes > 0 or comments > 0):
                ratio = (comments + likes) / views
                item["engagement_ratio"] = round(ratio * 100, 2)  # 百分比形式
                item["ratio_available"] = True
            else:
                item["engagement_ratio"] = 0.0
                item["ratio_available"] = False

            # 【过滤泛娱乐大号逻辑】：
            # 若播放量巨大 (>15万) 但互动率极低 (<1.2%) 且专业密度命中 < 2，判定为泛娱乐/水视频并大幅降权
            is_bloat_entertainment = (
                views > 150_000
                and item["ratio_available"]
                and item["engagement_ratio"] < 1.2
                and item["density_hits"] < 2
            )
            if is_bloat_entertainment:
                item["rank_score"] = 0.05
            elif item["ratio_available"]:
                # 高互动比 * 语义密度加权
                item["rank_score"] = item["engagement_ratio"] * (1.0 + 0.35 * item["density_hits"])
            else:
                # 无法提取互动数时的纯语义密度兜底排序
                item["rank_score"] = 1.0 + item["density_hits"] * 0.8

            scored_list.append(item)
            time.sleep(random.uniform(0.4, 0.8))

        scored_list.sort(key=lambda x: x["rank_score"], reverse=True)
        adaptive_results[lang] = scored_list[:top_n_per_lang]
        del candidates
        gc.collect()

    return adaptive_results


# ==============================================================================
# 5. 二次媒体穿透、币安广场公共文本、Polymarket 与 Reddit 模块
# ==============================================================================
def fetch_secondary_and_social_intel(session: requests.Session) -> Dict[str, Any]:
    """
    【规则 2：第三方聚合媒体、币安广场公共文本与社区共识穿透】
    """
    intel: Dict[str, Any] = {
        "polymarket": [],
        "media_recaps": [],
        "binance_square_texts": [],
        "reddit_posts": [],
        "consensus_clusters": [],
    }

    # A. Polymarket Gamma API (活跃加密/宏观事件赔率)
    try:
        r = session.get(
            "https://gamma-api.polymarket.com/events",
            params={
                "active": "true",
                "closed": "false",
                "order": "volume24hr",
                "ascending": "false",
                "limit": 20,
            },
            timeout=10,
        )
        r.raise_for_status()
        target_kws = ("bitcoin", "btc", "fed", "rate", "crypto", "eth", "recession")
        for ev in r.json():
            title = ev.get("title", "")
            if any(k in title.lower() for k in target_kws):
                lead_odds = ""
                markets = ev.get("markets", [])
                if markets:
                    try:
                        outcomes = json.loads(markets[0].get("outcomes", "[]"))
                        prices = json.loads(markets[0].get("outcomePrices", "[]"))
                        if outcomes and prices:
                            lead_odds = f"{outcomes[0]}: {round(float(prices[0]) * 100, 1)}%"
                    except Exception:
                        pass
                intel["polymarket"].append(
                    {
                        "title": title,
                        "vol_24h": round(float(ev.get("volume24hr") or 0), 0),
                        "lead_odds": lead_odds,
                    }
                )
                if len(intel["polymarket"]) >= 4:
                    break
    except Exception as exc:
        logger.warning("Polymarket Gamma API 抓取失败: %s", exc)

    # B. 第三方行情复盘 RSS (英文 + 中文独立行情媒体聚合)
    rss_configs = [
        (
            "https://news.google.com/rss/search?q="
            + quote_plus("bitcoin analysts OR crypto sentiment OR spot etf outflow when:3d")
            + "&hl=en-US&gl=US&ceid=US:en"
        ),
        (
            "https://news.google.com/rss/search?q="
            + quote_plus("比特币 分析师 OR 爆仓 OR 抛压 OR 市场情绪 when:3d")
            + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        ),
        "https://cointelegraph.com/rss",
    ]
    seen_titles = set()
    for rss_url in rss_configs:
        try:
            r = session.get(rss_url, timeout=10)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for it in root.findall("./channel/item")[:4]:
                t_el = it.find("title")
                if t_el is not None and t_el.text:
                    clean_t = t_el.text.strip()
                    if clean_t not in seen_titles:
                        seen_titles.add(clean_t)
                        intel["media_recaps"].append(clean_t)
            del r
        except Exception as exc:
            logger.debug("RSS 抓取跳过 (%s): %s", rss_url[:40], exc)

    # C. 币安广场 (Binance Square) 公共文本穿透 (公开 feed + 站点 RSS 双保险)
    try:
        sq_resp = session.get(
            "https://www.binance.com/bapi/composite/v1/public/pgc/feed/recommended/query",
            params={"pageIndex": 1, "pageSize": 6},
            timeout=8,
        )
        if sq_resp.status_code == 200:
            sq_json = sq_resp.json()
            posts = sq_json.get("data", {}).get("vos", []) or []
            for p in posts:
                body = (p.get("title") or p.get("content") or "").strip()
                body = re.sub(r"\s+", " ", body)
                if body and any(k in body.lower() for k in ("btc", "bitcoin", "eth", "比特币", "仓位", "大盘")):
                    intel["binance_square_texts"].append(body[:110])
    except Exception:
        pass

    if not intel["binance_square_texts"]:
        # 若公开接口受地区 WAF 限制，自动通过 Google News 站点索引穿透币安广场公共文本
        try:
            sq_rss = (
                "https://news.google.com/rss/search?q="
                + quote_plus('site:binance.com/square (BTC OR 比特币 OR 仓位 OR ETF) when:7d')
                + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
            )
            r = session.get(sq_rss, timeout=10)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                for it in root.findall("./channel/item")[:4]:
                    t_el = it.find("title")
                    if t_el is not None and t_el.text:
                        intel["binance_square_texts"].append(t_el.text.strip()[:110])
        except Exception as exc:
            logger.debug("币安广场 RSS 穿透跳过: %s", exc)

    # D. Reddit r/Bitcoin 高热互动讨论
    try:
        r_headers = {
            "User-Agent": "python:zero_overhead_adaptive_sentiment:v2.0 (by /u/opensource_bot)"
        }
        r = session.get(
            "https://www.reddit.com/r/Bitcoin/hot.json?limit=8",
            headers=r_headers,
            timeout=10,
        )
        if r.status_code == 200:
            for ch in r.json().get("data", {}).get("children", []):
                d = ch.get("data", {})
                if d.get("stickied"):
                    continue
                intel["reddit_posts"].append(
                    {
                        "title": d.get("title", ""),
                        "score": int(d.get("score", 0)),
                        "comments": int(d.get("num_comments", 0)),
                    }
                )
                if len(intel["reddit_posts"]) >= 4:
                    break
    except Exception as exc:
        logger.warning("Reddit r/Bitcoin 抓取跳过: %s", exc)

    # E. 提炼全网高频共识主题聚类
    all_texts = (
        intel["media_recaps"]
        + intel["binance_square_texts"]
        + [p["title"] for p in intel["reddit_posts"]]
    )
    topic_counter: Counter = Counter()
    for txt in all_texts:
        low = txt.lower()
        for topic_name, kws in CONSENSUS_TOPICS.items():
            if any(k in low for k in kws):
                topic_counter[topic_name] += 1
    intel["consensus_clusters"] = topic_counter.most_common(4)

    gc.collect()
    return intel


# ==============================================================================
# 6. 交叉情绪诊断引擎
# ==============================================================================
def diagnose_sentiment(
    snapshot: Dict[str, Any],
    trends: Dict[str, List[Dict[str, Any]]],
    yt_data: Dict[str, List[Dict[str, Any]]],
    intel: Dict[str, Any],
) -> Dict[str, Any]:
    fgi = snapshot.get("fgi_now")

    buy_rows = trends.get("1_散户买入意向", [])
    fear_rows = trends.get("2_极端恐慌与洗盘", [])
    buy_avg_delta = round(sum(r["delta_pct"] for r in buy_rows) / len(buy_rows), 1) if buy_rows else 0.0
    fear_avg_delta = round(sum(r["delta_pct"] for r in fear_rows) / len(fear_rows), 1) if fear_rows else 0.0

    # 统计自适应抓取的高互动视频中恐慌 vs 亢奋比例
    all_yt = yt_data.get("EN", []) + yt_data.get("CN", [])
    yt_total = max(len(all_yt), 1)
    yt_panic_cnt = sum(1 for v in all_yt if v["panic_hits"] > v["bull_hits"])
    yt_bull_cnt = sum(1 for v in all_yt if v["bull_hits"] > v["panic_hits"])
    yt_panic_ratio = round((yt_panic_cnt / yt_total) * 100, 1)
    yt_bull_ratio = round((yt_bull_cnt / yt_total) * 100, 1)

    # 统计二次媒体与社区恐慌命中
    secondary_texts = intel.get("media_recaps", []) + intel.get("binance_square_texts", [])
    sec_panic = sum(_score_text(t)[0] for t in secondary_texts)
    sec_bull = sum(_score_text(t)[1] for t in secondary_texts)

    if fgi is not None and fgi <= 25:
        if yt_panic_ratio >= 30 or fear_avg_delta > 12 or sec_panic >= 3:
            tag = "[洗盘磨底/恐慌出局]"
            cross_note = (
                "高互动比专业频道与二次聚合媒体恐慌词频偏高，Fear & Greed 处于极度恐慌区，"
                "但 Web 端买入意向（buy bitcoin）未现增量脉冲，属于典型的场内去杠杆与筹码换手阶段。"
            )
            advice = (
                "严格规避高倍合约与纯情绪山寨；重点观察机构 ETF 资金流向是否止血及核心支撑有效性，"
                "保留充足稳定币冗余等待右侧确认。"
            )
        else:
            tag = "[老手横盘/无增量]"
            cross_note = "场外散户搜索冷清，高互动社区讨论偏谨慎沉闷，市场处于缩量阴跌或横盘期。"
            advice = "降低交易频率，避免在流动性匮乏区间反复磨损本金。"
    elif fgi is not None and fgi >= 75:
        if buy_avg_delta >= 20 or yt_bull_ratio >= 45:
            tag = "[极度FOMO/顶部特征]"
            cross_note = (
                "Web 端买币搜索动量与高互动视频乐观共识同时飙升，散户 FOMO 拥挤度显著升高。"
            )
            advice = "警惕流动性派发与插针回撤，建议分批止盈本金并收紧移动止损。"
        else:
            tag = "[增量爆发期]"
            cross_note = "多头氛围浓厚且高密度内容持续看多，但尚未达到全民盲目搜索的过热临界点。"
            advice = "顺势持有核心趋势现货，持续监控 `how to buy bitcoin` 是否突发直线飙升。"
    else:
        if buy_avg_delta > 15 and yt_bull_ratio > yt_panic_ratio:
            tag = "[增量爆发期]"
            cross_note = "Web 买盘意向温和抬升，专业分析与二次媒体偏向多头修复。"
            advice = "关注核心主流币种及有真实协议收入赛道的右侧突破机会。"
        elif sec_panic > sec_bull + 2 or yt_panic_ratio > yt_bull_ratio + 15:
            tag = "[老手横盘/无增量]"
            cross_note = "场内分析讨论偏防御或悲观，而外部 Web 新增搜索平淡，属于存量资金博弈。"
            advice = "多看少动，聚焦链上数据拐点与宏观政策落地节点。"
        else:
            tag = "[温和复苏/右侧观察]"
            cross_note = "Web 意图与高互动技术讨论处于中性平衡状态，等待下一宏观或资金面催化剂。"
            advice = "维持均衡仓位，密切跟踪高频共识主题的演变方向。"

    return {
        "tag": tag,
        "cross_note": cross_note,
        "advice": advice,
        "metrics": {
            "buy_avg_delta": buy_avg_delta,
            "fear_avg_delta": fear_avg_delta,
            "yt_panic_ratio": yt_panic_ratio,
            "yt_bull_ratio": yt_bull_ratio,
            "sec_panic": sec_panic,
            "sec_bull": sec_bull,
        },
    }


# ==============================================================================
# 7. 报告格式化与 Telegram 分段推送
# ==============================================================================
def build_html_report(
    snapshot: Dict[str, Any],
    trends: Dict[str, List[Dict[str, Any]]],
    yt_data: Dict[str, List[Dict[str, Any]]],
    intel: Dict[str, Any],
    diag: Dict[str, Any],
    elapsed_sec: float,
    peak_mem_mb: float,
) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    btc_p = f"${snapshot['btc_price']:,.2f}" if snapshot["btc_price"] else "N/A"
    btc_chg = f"{snapshot['btc_24h_pct']:+.2f}%" if snapshot["btc_24h_pct"] is not None else "N/A"
    btc_dom = f"{snapshot['btc_dominance']:.2f}%" if snapshot["btc_dominance"] is not None else "N/A"
    fgi_str = (
        f"{snapshot['fgi_now']} ({html.escape(snapshot['fgi_label'])})"
        if snapshot["fgi_now"] is not None
        else "N/A"
    )
    fgi_7d = f"{snapshot['fgi_7d_ago']}" if snapshot["fgi_7d_ago"] is not None else "N/A"
    m = diag["metrics"]

    lines: List[str] = [
        "<b>📊 自适应加密情绪与多渠道情报日报 (Zero Hardcoding)</b>",
        f"🕒 时间: <code>{now_str}</code> | 地区: <code>{TRENDS_GEO or 'Global'}</code>",
        f"₿ BTC: <b>{btc_p}</b> (24h: {btc_chg} | 市占率: {btc_dom})",
        f"😨 恐慌贪婪指数: <b>{fgi_str}</b> (7日前: {fgi_7d})",
        "",
        f"🏷 <b>标准情绪标签: {html.escape(diag['tag'])}</b>",
        f"🔍 <b>交叉诊断结论</b>: {html.escape(diag['cross_note'])}",
        f"🛡 <b>操作风控提醒</b>: {html.escape(diag['advice'])}",
        "",
        "<b>一、【Web端 Google Trends 4大意图 (7日动量)】</b>",
    ]

    if not any(trends.values()):
        lines.append("⚠️ Google Trends 本轮临时受限流影响，已自动平滑跳过。")
    else:
        for g_name, rows in trends.items():
            lines.append(f"• <u>{html.escape(g_name)}</u>")
            for r in rows:
                arrow = "🔺" if r["delta_pct"] > 10 else ("🔻" if r["delta_pct"] < -10 else "▪️")
                lines.append(
                    f"  {arrow} <code>{html.escape(r['kw'])}</code>: 最新 {r['latest']} "
                    f"(7日均 {r['avg_7d']} | 变化 {r['delta_pct']:+.1f}%)"
                )

    lines.append("")
    lines.append(
        f"<b>二、【YouTube 自适应高互动视频精选】</b> "
        f"(恐慌占比 {m['yt_panic_ratio']}% | 亢奋 {m['yt_bull_ratio']}%)"
    )
    lines.append("<i>排序依据: 语义密度匹配 × 真实互动比 (评论+点赞)/播放量</i>")

    for lang, label in (("EN", "英文高密度语义精选"), ("CN", "中文高密度语义精选")):
        lines.append(f"• <b>{label}</b>")
        vids = yt_data.get(lang, [])
        if not vids:
            lines.append("  - <i>本轮未检索到符合过滤门槛的近期分析视频</i>")
            continue
        for v in vids:
            flag = "🔴" if v["panic_hits"] > v["bull_hits"] else ("🟢" if v["bull_hits"] > v["panic_hits"] else "⚪")
            ratio_str = (
                f"互动率 {v['engagement_ratio']}%"
                if v["ratio_available"]
                else f"语义密度 {v['density_hits']}"
            )
            ch_esc = html.escape(v["channel"][:24])
            t_esc = html.escape(v["title"][:68])
            pub_esc = html.escape(v["published"])
            lines.append(
                f"  - {flag} [{ratio_str} | 👁{v['views']:,}] "
                f"<a href=\"{v['url']}\">{t_esc}</a> <i>({ch_esc}, {pub_esc})</i>"
            )

    lines.append("")
    lines.append("<b>三、【二次聚合媒体、币安广场与预测市场共识】</b>")

    if intel["consensus_clusters"]:
        cluster_str = " | ".join(
            f"{html.escape(k)}({cnt})" for k, cnt in intel["consensus_clusters"]
        )
        lines.append(f"• 🔥 <u>全网高频共识聚类</u>: {cluster_str}")

    if intel["polymarket"]:
        lines.append("• <u>Polymarket 活跃宏观/加密盘口</u>")
        for pm in intel["polymarket"][:3]:
            odds = f" ({html.escape(pm['lead_odds'])})" if pm["lead_odds"] else ""
            lines.append(
                f"  - {html.escape(pm['title'][:65])}{odds} | 24h量 ${pm['vol_24h']:,.0f}"
            )

    if intel["binance_square_texts"]:
        lines.append("• <u>币安广场公共文本穿透</u>")
        for sq in intel["binance_square_texts"][:3]:
            lines.append(f"  - {html.escape(sq)}")

    if intel["media_recaps"]:
        lines.append("• <u>第三方行情复盘与新闻 RSS</u>")
        for mr in intel["media_recaps"][:4]:
            lines.append(f"  - {html.escape(mr[:95])}")

    if intel["reddit_posts"]:
        lines.append("• <u>Reddit r/Bitcoin 社区脉搏</u>")
        for rp in intel["reddit_posts"][:3]:
            lines.append(
                f"  - {html.escape(rp['title'][:80])} (👍{rp['score']} / 💬{rp['comments']})"
            )

    lines.append("")
    lines.append(
        f"<i>⚙️ Zero-API-Key 运行完毕 | 耗时: {elapsed_sec:.1f}s | 峰值内存增量: {peak_mem_mb:.1f} MB</i>"
    )
    return "\n".join(lines)


def send_telegram_message(text: str) -> bool:
    if (
        not TELEGRAM_BOT_TOKEN
        or "YOUR_TELEGRAM_BOT_TOKEN" in TELEGRAM_BOT_TOKEN
        or not TELEGRAM_CHAT_ID
        or "YOUR_TELEGRAM_CHAT_ID" in TELEGRAM_CHAT_ID
    ):
        logger.warning("未配置 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，仅在终端输出报告。")
        return False

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    max_len = 3800
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0

    for line in text.splitlines():
        l_len = len(line) + 1
        if cur_len + l_len > max_len and cur:
            chunks.append("\n".join(cur))
            cur = [line]
            cur_len = l_len
        else:
            cur.append(line)
            cur_len += l_len
    if cur:
        chunks.append("\n".join(cur))

    ok_all = True
    for idx, chunk in enumerate(chunks, start=1):
        try:
            r = requests.post(
                api_url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            if r.status_code != 200:
                logger.error("Telegram 第 %d/%d 段推送失败: %s", idx, len(chunks), r.text)
                ok_all = False
            else:
                logger.info("Telegram 第 %d/%d 段推送成功。", idx, len(chunks))
            time.sleep(0.5)
        except Exception as exc:
            logger.error("Telegram 推送异常: %s", exc)
            ok_all = False
    return ok_all


# ==============================================================================
# 8. 主入口
# ==============================================================================
def main() -> int:
    tracemalloc.start()
    t0 = time.time()
    logger.info("启动 100% 自适应零成本加密情绪 Agent...")

    with requests.Session() as session:
        session.headers.update(HTTP_HEADERS)

        logger.info("[1/4] 抓取行情基准与恐慌贪婪指数...")
        snapshot = fetch_market_snapshot(session)

        logger.info("[2/4] 抓取 Web 端 4 大意图 Google Trends...")
        trends = fetch_google_trends()

        logger.info("[3/4] 执行 YouTube 语义图谱检索与互动比过滤...")
        yt_data = fetch_adaptive_youtube(session, top_n_per_lang=4)

        logger.info("[4/4] 执行第三方媒体 RSS、币安广场、Polymarket 与 Reddit 穿透...")
        intel = fetch_secondary_and_social_intel(session)

    diag = diagnose_sentiment(snapshot, trends, yt_data, intel)
    elapsed_sec = time.time() - t0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mem_mb = peak_bytes / (1024 * 1024)

    report_html = build_html_report(
        snapshot=snapshot,
        trends=trends,
        yt_data=yt_data,
        intel=intel,
        diag=diag,
        elapsed_sec=elapsed_sec,
        peak_mem_mb=peak_mem_mb,
    )

    plain = re.sub(r"</?(b|u|i|code)>", "", report_html)
    print("\n" + "=" * 68)
    print(plain)
    print("=" * 68 + "\n")

    send_telegram_message(report_html)
    return 0


if __name__ == "__main__":
    sys.exit(main())