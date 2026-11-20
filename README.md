# Zero-Overhead Crypto Sentiment Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Zero API Key](https://img.shields.io/badge/API%20Key-100%25%20Free%20%26%20Zero%20Key-brightgreen.svg)]()
[![Algorithm](https://img.shields.io/badge/KOL%20Filtering-100%25%20Adaptive%20%2F%20No%20Hardcoding-purple.svg)]()

[简体中文](#简体中文) | [English](#english)

---

## <a name="简体中文"></a>简体中文

一个专为**老旧 PC（如 i7-4770）、树莓派（Raspberry Pi）及超低内存 VPS（<50MB 增量内存）**设计的 100% 免 API Key、零使用成本、全自适应加密货币多渠道情绪与叙事诊断 Agent。

### 🧠 架构设计与中立算法机制

> **中立性声明**：本开源项目**绝不针对或硬编码任何特定 KOL**。所有 YouTube 及社媒情报的提取，均基于【语义密度匹配】、【第三方引用穿透】与【社区真实互动比（Engagement Ratio）】三大中立规则自动筛选呈现。

1. **语义图谱与专用索引匹配（Semantic Relevance）**：
   * 不绑定任何个人频道 URL 或博主名称，完全使用高信息密度专业检索图谱（例如英文 `"bitcoin macro metrics OR liquidation OR MVRV OR SOPR"`，中文 `"比特币 链上指标 共振 仓位 破位"`），结合专业术语密度词典直接锁定链上、宏观与流动性讨论。
2. **第三方引用穿透与共识聚类（Secondary Media Amplification）**：
   * 穿透第三方行情复盘 RSS（Google News 聚合 / CoinTelegraph）、币安广场（Binance Square）公共文本流及 Reddit `r/Bitcoin` 高热帖子，通过确定性主题词簇统计当前全网高频共振焦点（如 ETF 净流出、衍生品爆仓、宏观利率与机构持仓）。
3. **信息密度与社区真实互动比过滤（Engagement Ratio Filter）**：
   * 自动剔除时长小于 90 秒的短视频碎片，并轻量提取视频真实播放量、点赞数与评论数，计算 `Engagement Ratio = (Comments + Likes) / Views`。对高播放量但低互动率且缺乏专业术语的泛娱乐大号自动降权，优先呈现真实极客与交易社区高频互动的分析观点。

### ✨ 核心特性

* **💸 100% 零 API Key / 零成本**：无需 OpenAI、Gemini 或任何付费数据 API，完全依托 `pytrends`、`scrapetube`、`requests` 及免费公开数据接口。
* **⚡ 极致低开销**：无 GPU、无无头浏览器，即时正则提取并主动触发 `gc.collect()` 内存回收，通过 `tracemalloc` 实测峰值内存增量通常低于 50MB。
* **🧭 Web 4 大核心搜索意图 + 7 日动量**：全面监测 `散户买入意向`、`极端恐慌与洗盘`、`宏观机构叙事` 与 `山寨与垂直投机` 相对于 7 日均值的变化率（`delta_pct`），并支持在 `EXTRA_KEYWORDS` 随时追加热词。
* **🔮 跨平台情报整合**：集成 Alternative.me 恐慌贪婪指数、CoinGecko/Coinbase 现货与市占率、Polymarket 活跃盘口赔率与 24h 成交量。
* **📲 Telegram 安全分段推送**：自动 HTML 转义并按 3800 字符上限智能切分长消息推送至 Telegram。

---

### 🚀 快速开始（Quick Start）

#### 1. 克隆仓库
```bash
git clone https://github.com/your-username/zero-overhead-crypto-sentiment-agent.git
cd zero-overhead-crypto-sentiment-agent
```

#### 2. 安装依赖
建议使用 Python 3.9+：
```bash
pip install pytrends scrapetube requests
```

#### 3. 配置环境变量
向 Telegram `@BotFather` 申请 `TELEGRAM_BOT_TOKEN`，向 `@userinfobot` 获取 `TELEGRAM_CHAT_ID`。

* **Linux / macOS**：
```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
export TELEGRAM_CHAT_ID="987654321"
export TRENDS_GEO=""  # 留空代表全球，填 "US" 代表美国
```

* **Windows (CMD)**：
```cmd
set TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
set TELEGRAM_CHAT_ID=987654321
set TRENDS_GEO=
```
*(也可直接修改 `run_agent.py` 顶部的常量默认值。)*

#### 4. 运行方式
* **直接执行 Python**：
```bash
python run_agent.py
```
* **Windows 批处理 (`run_agent.bat`)**：
在同级目录新建 `run_agent.bat` 填入以下内容后即可双击运行或用于系统计划任务：
```bat
@echo off
cd /d "%~dp0"
set TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
set TELEGRAM_CHAT_ID=987654321
set TRENDS_GEO=
python run_agent.py >> agent.log 2>&1
```

---

### ⏰ 定时任务配置

#### Linux / 树莓派 (Cron)
运行 `crontab -e`，添加每日定时任务（例如每天 09:00 执行）：
```cron
0 9 * * * TELEGRAM_BOT_TOKEN="你的Token" TELEGRAM_CHAT_ID="你的ChatID" /usr/bin/python3 /path/to/zero-overhead-crypto-sentiment-agent/run_agent.py >> /path/to/zero-overhead-crypto-sentiment-agent/agent.log 2>&1
```

#### Windows 任务计划程序 (Task Scheduler)
1. 按 `Win + R` 运行 `taskschd.msc`，点击右侧 **“创建基本任务”**。
2. 触发器设为 **“每天”**，选择期望推送时间。
3. 操作选择 **“启动程序”**，程序路径指向 `run_agent.bat`（并在 **“起始于”** 填入项目文件夹绝对路径）。
4. 建议在属性中勾选 *“如果错过计划，立即启动任务”*。

---

## <a name="english"></a>English

A **100% API-Key-Free, Zero-Cost, Fully Adaptive** crypto retail sentiment and multi-channel intelligence agent built for legacy hardware (e.g., Intel i7-4770, old PCs, Raspberry Pi, or <50MB RAM VPS).

### 🧠 Architecture & Neutral Filtering Engine

> **Neutrality Statement**: This open-source project **NEVER targets or hardcodes any specific KOLs**. All YouTube and social intelligence extraction is driven autonomously by three neutral mechanisms: **Semantic Relevance Matching**, **Secondary Media Amplification**, and **Community Engagement Ratio Filtering**.

1. **Semantic Relevance Matching**:
   * Zero hardcoded channel URLs or creator names. Queries are constructed purely from high-information-density analytical graphs (e.g., `"bitcoin macro metrics OR liquidation OR MVRV OR SOPR"` and Chinese on-chain equivalents) scored against technical/macro lexicons.
2. **Secondary Media Amplification**:
   * Penetrates third-party market recap RSS feeds, Binance Square public text feeds, and Reddit `r/Bitcoin` hot discussions to cluster high-frequency market consensus themes (e.g., ETF flows, liquidations, macro rates, institutional positioning).
3. **Engagement Ratio Filter**:
   * Filters out short-form noise (<90s) and extracts views, likes, and comments to calculate `Engagement Ratio = (Comments + Likes) / Views`. High-view generic entertainment channels with low engagement and low analytical density are automatically penalized in favor of high-interaction technical discussions.

### ✨ Highlights

* **100% Zero API Key**: Runs solely on `pytrends`, `scrapetube`, `requests`, and free public endpoints (Alternative.me FGI, CoinGecko/Coinbase, Polymarket Gamma API, RSS, Reddit JSON).
* **Zero Overhead**: Pure HTTP text parsing with explicit `gc.collect()` memory management (<50MB incremental RAM measured via `tracemalloc`).
* **4 Search Intents + 7-Day Momentum**: Tracks `Retail Buy Intent`, `Extreme Fear & Capitulation`, `Macro & Institutional`, and `Altcoin & Speculation` against their 7-day baseline (`delta_pct`), plus customizable `EXTRA_KEYWORDS`.
* **Safe Chunked Telegram Push**: Auto-escapes HTML and splits long diagnostics into `<=3800`-character chunks.

---

### 🚀 Quick Start

#### 1. Clone & Install
```bash
git clone https://github.com/your-username/zero-overhead-crypto-sentiment-agent.git
cd zero-overhead-crypto-sentiment-agent
pip install pytrends scrapetube requests
```

#### 2. Configure Environment Variables
Obtain `TELEGRAM_BOT_TOKEN` from `@BotFather` and `TELEGRAM_CHAT_ID` from `@userinfobot`.

```bash
# Linux / macOS
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export TRENDS_GEO=""  # "" for Global, "US" for United States
python run_agent.py
```

For Windows, create `run_agent.bat`:
```bat
@echo off
cd /d "%~dp0"
set TELEGRAM_BOT_TOKEN=your_bot_token
set TELEGRAM_CHAT_ID=your_chat_id
set TRENDS_GEO=
python run_agent.py >> agent.log 2>&1
```

#### 3. Scheduling
* **Linux Cron (`crontab -e`)**:
```cron
0 9 * * * TELEGRAM_BOT_TOKEN="your_token" TELEGRAM_CHAT_ID="your_chat_id" /usr/bin/python3 /path/to/run_agent.py >> /path/to/agent.log 2>&1
```
* **Windows Task Scheduler**: Open `taskschd.msc` → Create Basic Task → Daily → Start `run_agent.bat` (set *Start in* to your repo folder).

### ⚠️ Disclaimer
For research and informational purposes only. Not financial advice.

### 📄 License
MIT License — see [LICENSE](LICENSE).