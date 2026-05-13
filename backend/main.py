"""熔炉 Crucible — FastAPI 后端

从"思维擂台"进化为"熔炉"：争议话题碰撞引擎
苏格拉底式追问，3轮碰撞，前后立场对比
"""
import logging
import json
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from zhihu_api import ZhihuClient
from zhihu_hackathon_api import ZhihuHackathonClient
from crucible_engine import CrucibleEngine, VerdictRequest
import zhihu_oauth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Globals ────────────────────────────────────────────

hackathon_client: Optional[ZhihuHackathonClient] = None
crucible: Optional[CrucibleEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global hackathon_client, crucible
    hackathon_client = ZhihuHackathonClient()
    crucible = CrucibleEngine(zhihu_client=hackathon_client)
    logger.info("Crucible backend started")
    yield


app = FastAPI(title="熔炉 Crucible", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Models ─────────────────────────────────────

class CrashStart(BaseModel):
    topic_id: str
    initial_stance: str = "undecided"  # "pro" | "con" | "neutral" | "undecided"


class VerdictBody(BaseModel):
    winner: str              # "pro" | "con" | "tie" | "both_changed"
    initial_stance: str
    final_stance: str
    mind_changed: bool
    comment: str = ""


class PublishBody(BaseModel):
    pass  # crash_id from path


# ── Auth helpers ────────────────────────────────────────

from fastapi import Request, Response
from fastapi.responses import RedirectResponse

SESSION_COOKIE = "crucible_session"


def get_current_user(request: Request) -> Optional[dict]:
    """Extract current user from session cookie (optional, returns None if not logged in)"""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return zhihu_oauth.verify_session_token(token)


# ── OAuth Routes ───────────────────────────────────────

@app.get("/api/auth/zhihu/url")
async def auth_zhihu_url():
    """生成知乎授权跳转 URL"""
    result = zhihu_oauth.get_authorize_url()
    return result


@app.get("/api/auth/zhihu/callback")
async def auth_zhihu_callback(code: str = "", state: str = ""):
    """知乎 OAuth 回调：换 token → 获取用户 → 写 cookie → 跳首页"""
    if not code or not state:
        return RedirectResponse(url="/", status_code=302)

    # Verify state (CSRF)
    if not zhihu_oauth.verify_state(state):
        logger.warning("OAuth callback: invalid state")
        return RedirectResponse(url="/?auth=error", status_code=302)

    # Exchange code for token
    access_token = zhihu_oauth.exchange_code(code)
    if not access_token:
        return RedirectResponse(url="/?auth=error", status_code=302)

    # Get user info
    user = zhihu_oauth.get_user_info(access_token)
    if not user:
        return RedirectResponse(url="/?auth=error", status_code=302)

    # Create session token
    session_token = zhihu_oauth.create_session_token(user)

    logger.info(f"OAuth login: uid={user.uid} name={user.fullname}")

    # Redirect to home with session cookie
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        max_age=2592000,  # 30 days
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return resp


@app.get("/api/auth/me")
async def auth_me(request: Request):
    """获取当前登录用户信息"""
    user = get_current_user(request)
    if user:
        return {"logged_in": True, "user": user}
    return {"logged_in": False, "user": None}


@app.post("/api/auth/logout")
async def auth_logout():
    """登出（清除 cookie）"""
    resp = Response(json.dumps({"ok": True}), media_type="application/json")
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ── Routes ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Crucible"}


@app.get("/api/topics")
async def get_topics():
    """获取争议话题列表（预置 + 热榜）"""
    topics = crucible.get_topics()
    return {"topics": topics, "count": len(topics)}


@app.post("/api/crash")
async def start_crash(req: CrashStart, request: Request):
    """开始一场碰撞"""
    user = get_current_user(request)
    user_id = str(user["uid"]) if user else None
    result = crucible.start_crash(req.topic_id, req.initial_stance, user_id=user_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/crash/{crash_id}/round/{round_number}")
async def get_round(crash_id: str, round_number: int):
    """获取第N轮碰撞内容"""
    result = crucible.get_round(crash_id, round_number)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/api/crash/{crash_id}/verdict")
async def submit_verdict(crash_id: str, body: VerdictBody):
    """用户评判：谁说服了你？你的想法变了吗？"""
    verdict = VerdictRequest(
        crash_id=crash_id,
        winner=body.winner,
        initial_stance=body.initial_stance,
        final_stance=body.final_stance,
        mind_changed=body.mind_changed,
        comment=body.comment,
    )
    result = crucible.submit_verdict(verdict)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/crash/{crash_id}/record")
async def get_record(crash_id: str):
    """获取碰撞记录（公开化，制度种子）"""
    result = crucible.get_record(crash_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/crash/{crash_id}/share")
async def share_record(crash_id: str):
    """返回分享页数据"""
    result = crucible.get_record(crash_id)
    if "error" in result:
        raise HTTPException(404, result["error"])

    # Extract all arguments for golden quote auto-selection
    all_args = []
    for r in result["rounds"]:
        all_args.append({"text": r["pro_argument"], "side": "pro", "round": r["round"]})
        all_args.append({"text": r["con_argument"], "side": "con", "round": r["round"]})

    # Sort by length (shortest first = most punchy)
    all_args.sort(key=lambda x: len(x["text"]))
    golden_default = all_args[0] if all_args else None

    return {
        "crash_id": result["crash_id"],
        "topic_title": result["topic_title"],
        "rounds": result["rounds"],
        "before_after": result.get("before_after", {}),
        "verdict": result.get("verdict"),
        "reflection": (result.get("verdict") or {}).get("comment", ""),
        "golden_default": golden_default,
    }


@app.post("/api/crash/{crash_id}/publish")
async def publish_to_ring(crash_id: str):
    """发布碰撞记录到知乎圈子"""
    record = crucible.get_record(crash_id)
    if "error" in record:
        raise HTTPException(404, record["error"])

    # Build content
    lines = [f"🔥 熔炉碰撞记录：「{record['topic_title']}」\n"]
    for r in record["rounds"]:
        lines.append(f"【第{r['round']}轮】")
        lines.append(f"  正方：{r['pro_argument']}")
        lines.append(f"  反方：{r['con_argument']}")
        lines.append("")

    ba = record.get("before_after", {})
    if ba:
        lines.append(f"初始立场：{ba.get('initial_stance', '?')} → 最终立场：{ba.get('final_stance', '?')}")

    verdict = record.get("verdict")
    if verdict and verdict.get("comment"):
        lines.append(f"评判：{verdict['comment']}")

    lines.append("\n—— 由「熔炉 Crucible」生成 | #知乎黑客松2026")

    content = "\n".join(lines)
    result = hackathon_client.post_pin(content)
    if result:
        crucible.mark_published(crash_id)
        return {"status": "published", "data": result}
    return {"status": "published_mock", "message": "模拟发布成功（开赛后接入真实API）"}


# ── Preserved routes ───────────────────────────────────

@app.get("/api/hot")
async def get_hot_topics():
    """获取知乎热榜"""
    hot = hackathon_client.get_hot_list(hours=24)
    return {
        "topics": [
            {"title": h.title, "hot_score": h.hot_score, "url": h.url}
            for h in hot[:10]
        ],
    }


@app.get("/api/usage")
async def get_usage():
    """API 用量监控（100次/天限制）"""
    return hackathon_client.get_usage_stats()


# ── Run ────────────────────────────────────────────────

# ── Serve Frontend ─────────────────────────────────────

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_frontend = Path(__file__).parent.parent / "frontend" / "dist"
if not _frontend.exists():
    _frontend = Path(__file__).parent.parent / "frontend-dist"

@app.get("/")
async def serve_index():
    return FileResponse(_frontend / "index.html")


# Static assets (js, css, etc.)
app.mount("/assets", StaticFiles(directory=_frontend / "assets"), name="assets")


# SPA favicon/icons
for _static_file in ["favicon.svg", "icons.svg", "vite.svg"]:
    _fp = _frontend / _static_file
    if _fp.exists():
        _make_route = lambda p=_fp: FileResponse(p)
        app.get(f"/{_static_file}")(lambda p=_fp: FileResponse(p))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)


# ── Static data (pre-generated) ──────────────────────

@app.get("/api/static")
async def get_static_data():
    """预生成的静态碰撞数据（秒开）"""
    from pathlib import Path as P
    static_file = P(__file__).parent.parent / "data" / "static_crashes.json"
    if static_file.exists():
        return json.loads(static_file.read_text())
    return []


class SearchTopicRequest(BaseModel):
    query: str


class ArmRequest(BaseModel):
    """用户不服点 -> AI 武装论据"""
    topic: str                # 碰撞话题
    user_stance: str          # 用户的立场（pro/con）
    grievance: str = ""       # 用户的不服描述
    target_argument: str = "" # 用户不服的具体论点


@app.post("/api/arm")
async def arm_user(req: ArmRequest):
    """不服 -> 武装：用户输入不服点，AI 搜索知乎来源并返回论据"""
    if not hackathon_client:
        raise HTTPException(503, "API not available")

    # 1. 搜索知乎真实回答
    search_query = f"{req.topic} {req.grievance or ''}"
    results = hackathon_client.search(search_query, limit=10)
    sources = [{"title": r.title, "url": r.url, "author": r.author, "summary": r.summary} for r in results[:5]]

    # 2. 构造武装 prompt
    answers_text = ""
    if results:
        answers_text = "\n---\n".join([f"【{r.author or '匿名'}】{r.summary[:300]}" for r in results[:6]])

    stance_label = "正方" if req.user_stance == "pro" else "反方"
    prompt = f"""用户在碰撞话题「{req.topic}」中站{stance_label}。
{'用户不服的论点是：' + req.target_argument if req.target_argument else ''}
{'用户的不服理由：' + req.grievance if req.grievance else ''}

{'以下是知乎上相关回答，请从中提取支撑用户立场的论据：\n' + answers_text if answers_text else '请提供支撑该立场的论据。'}

严格要求：
1. 返回 3 条论据，每条必须简短有力（1-2句话）
2. 每条标注来源（有知乎回答时用【作者名】标注）
3. 论据必须有说服力，不是泛泛而谈

严格输出 JSON：
{{"arguments":[{{"point":"论点内容","source":"来源说明"}}]}}"""

    import json as _json
    armed_args = []
    raw_text = hackathon_client.deepseek_chat(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    )

    if raw_text:
        try:
            json_str = raw_text
            if "```json" in raw_text:
                json_str = raw_text.split("```json")[1].split("```")[0]
            elif "```" in raw_text:
                json_str = raw_text.split("```")[1].split("```")[0]
            data = _json.loads(json_str.strip())
            armed_args = data.get("arguments", [])
        except Exception:
            pass

    if not armed_args:
        # Fallback
        armed_args = [
            {"point": f"基于你的立场分析，这个判断有合理的逻辑基础", "source": "AI 分析"},
        ]

    return {
        "topic": req.topic,
        "stance": req.user_stance,
        "arguments": armed_args[:3],
        "sources": sources[:3],
        "slogan": "在熔炉碰撞后形成的观点",
    }


@app.post("/api/search-topic")
async def search_and_crash(req: SearchTopicRequest):
    """搜索入口：用户输入关键词，实时生成碰撞"""
    if not hackathon_client:
        raise HTTPException(503, "API not available")
    
    # 搜索真实回答
    results = hackathon_client.search(req.query, limit=10)
    if not results:
        raise HTTPException(404, f"No results for '{req.query}'")
    
    # 用 DeepSeek 提取正反方论点
    answers_text = "\n---\n".join([f"【{r.author or '匿名'}】{r.summary[:300]}" for r in results[:8]])
    
    extract_prompt = f"""分析以下知乎搜索结果，提取正方和反方核心论点。

话题：{req.query}
搜索结果：
{answers_text}

严格输出JSON：
{{"pro_args":["正方论点1","正方论点2","正方论点3"],"con_args":["反方论点1","反方论点2","反方论点3"],"consensus":["共识点"]}}"""

    extracted = hackathon_client.deepseek_chat(
        messages=[{"role":"user","content":extract_prompt}],
        max_tokens=800,
    )
    
    import json as _json
    pro_args = []
    con_args = []
    sources = [{"title":r.title,"url":r.url,"author":r.author} for r in results[:5]]
    
    if extracted:
        try:
            data = _json.loads(extracted)
            pro_args = data.get("pro_args",[])
            con_args = data.get("con_args",[])
        except:
            pass
    
    if not pro_args or not con_args:
        raise HTTPException(500, "Failed to extract arguments")
    
    # 用 DeepSeek 生成 3 轮碰撞
    rounds = []
    prev_pro = " | ".join(pro_args)
    prev_con = " | ".join(con_args)
    
    round_prompts = [
        ("开场立论", f"你是正方和反方的辩论者。话题：{req.query}\n正方论点：{prev_pro}\n反方论点：{prev_con}\n\n分别给出最强论点（2-3句话）。JSON: {{\"pro\":\"...\",\"con\":\"...\"}}"),
        ("针锋相对", f"上一轮：\n正方：{prev_pro}\n反方：{prev_con}\n\n各自反驳对方。先承认对方有理，再用'如果从X角度看呢？'追问。JSON: {{\"pro\":\"...\",\"con\":\"...\"}}"),
        ("最终陈词", f"最终轮：修正立场，承认对方有理的部分。JSON: {{\"pro\":\"...\",\"con\":\"...\"}}"),
    ]
    
    for label, prompt in round_prompts:
        resp = hackathon_client.deepseek_chat(
            messages=[{"role":"user","content":prompt}],
            max_tokens=600,
        )
        if resp:
            try:
                d = _json.loads(resp)
                rounds.append({"round":len(rounds)+1,"pro_argument":d.get("pro",""),"con_argument":d.get("con","")})
                prev_pro = d.get("pro","")
                prev_con = d.get("con","")
            except:
                pass
    
    return {
        "title": req.query,
        "pro_label": "正方",
        "con_label": "反方",
        "rounds": rounds,
        "sources": sources,
    }
