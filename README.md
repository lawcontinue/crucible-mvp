# 🔥 熔炉 Crucible — AI 时代的观点碰撞引擎

> 输入一个争议话题，围观 AI 从不同立场碰撞，发现自己的想法变了。

## 一句话

**人是辩手，AI 是镜子。** 熔炉不替你说话，帮你看到对面的最强论据。

## 核心体验

1. **选话题** — 从知乎热榜、搜索、或预置话题中选择
2. **站队** — 选一个初始立场
3. **围观碰撞** — AI 正反方三轮交锋（开场立论 → 针锋相对 → 最终陈词）
4. **再站队** — 看完碰撞后，你的立场变了吗？
5. **生成记录** — 碰撞前 vs 碰撞后，立场变化一目了然

## 产品亮点

| 亮点 | 说明 |
|------|------|
| 🔗 知乎原生 | 接入知乎搜索 + 热榜 API，论据来自真实知乎回答 |
| 🧠 DeepSeek 引擎 | 结构化论点提取 + 苏格拉底式碰撞生成 |
| 👤 创作者溯源 | 每个论据标注知乎作者信息（姓名/专业/年限/链接） |
| 🏷️ AI 透明标识 | 碰撞论点标注"AI 生成分析"，遵守《标识办法》 |
| ⚡ 秒开体验 | 7 个话题预生成静态数据，零等待 |
| 🔍 实时生成 | 搜索入口支持任意话题，实时调用 DeepSeek 生成碰撞 |
| 📊 立场追踪 | 记录用户碰撞前后立场变化，量化"想法变了" |

## 技术栈

```
前端: React + Vite + CSS（无框架，纯手写）
后端: FastAPI + Python 3.14
数据: 知乎开放平台 API（搜索/热榜）+ DeepSeek API
缓存: JSON 文件缓存（应对 API 日限额）
```

## 架构

```
用户 → React 前端 → FastAPI 后端
                      ├── /api/static       ← 预生成数据（秒开）
                      ├── /api/search-topic ← 搜索实时生成
                      ├── /api/topics       ← 话题列表（热榜+预置）
                      └── CrucibleEngine    ← 碰撞引擎核心
                            ├── 知乎搜索 → 真实回答
                            ├── DeepSeek → 论点提取
                            └── DeepSeek → 3轮碰撞生成
```

## 碰撞引擎流程

```
Step 1: 搜索知乎真实回答（top 10，按点赞排序）
Step 2: DeepSeek 提取正反方论点（标注来源作者）
Step 3: 基于真实论点生成 3 轮碰撞
  ├── Round 1: 开场立论（最强论点）
  ├── Round 2: 针锋相对（先承认对方有力点，再反驳）
  └── Round 3: 最终陈词（修正立场，找共识）
Fallback: 无真实回答时降级为纯 LLM 生成
```

## 预置话题（7 个）

| # | 话题 | 类型 |
|---|------|------|
| 1 | AI 会不会取代程序员？ | 技术/职业 |
| 2 | 远程办公是不是未来的唯一方向？ | 工作 |
| 3 | 学历贬值是事实还是错觉？ | 教育 |
| 4 | 应该对所有 AI 生成内容强制标注吗？ | AI/法律 |
| 5 | 全民基本收入（UBI）在中国可行吗？ | 经济 |
| 6 | **AI 生成的法律建议能用吗？** | ⚖️ 高 stakes |
| 7 | **35 岁被裁，该创业还是打工？** | 💼 高 stakes |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/static` | GET | 获取预生成的静态碰撞数据 |
| `/api/topics` | GET | 获取话题列表（热榜+预置） |
| `/api/search-topic` | POST | 搜索话题并实时生成碰撞 |
| `/api/start-crash` | POST | 开始碰撞（后端引擎） |
| `/api/round/{crash_id}/{n}` | GET | 获取第 N 轮碰撞 |
| `/api/verdict` | POST | 提交用户评判 |
| `/api/record/{crash_id}` | GET | 获取碰撞完整记录 |
| `/health` | GET | 健康检查 |

## 本地运行

```bash
# 后端
cd backend
pip install -r requirements.txt
python main.py  # 默认 8003 端口

# 前端
cd frontend
npm install
npm run dev  # 默认 5173 端口
```

## 环境变量

```env
# .env 文件
ZHIHU_API_KEY=xxx          # 知乎开放平台 API Key
DEEPSEEK_API_KEY=xxx       # DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

## AI 透明声明

- 碰撞论点由 DeepSeek 基于知乎真实回答分析生成，非原文
- 引用来源标注了知乎原作者及链接
- 遵守《深度合成服务标识办法》要求
- 产品定位：AI 是镜子不是演员，人不跟 AI 辩，AI 帮你看清对面

## License

MIT

---

**知乎黑客松 2026 · 熔炉 Crucible 队**
