"""知乎黑客松 API 客户端 — 基于官方开放接口

Base URL: https://openapi.zhihu.com/
鉴权: HMAC-SHA256 签名（X-App-Key + X-Timestamp + X-Log-Id + X-Sign + X-Extra-Info）

圈子 ID:
- 2001009660925334090 OpenClaw 人类观察员
- 2015023739549529606 A2A for Reconnect
- 2029619126742656657 黑客松脑洞补给站

限制：全局限流 10 QPS
"""
import os
import time
import json
import hashlib
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果条目"""
    title: str
    summary: str
    author: str
    url: str
    voteup_count: int
    comment_count: int
    relevance_score: float
    authority_level: str = ""
    selected_comments: List[str] = field(default_factory=list)


@dataclass
class HotItem:
    """热榜条目"""
    title: str
    hot_score: float
    url: str
    summary: str
    voteup_count: int = 0
    comment_count: int = 0


class CacheManager:
    """文件缓存管理器 — 应对 100次/天 的严格限制"""

    def __init__(self, cache_dir: str = None, default_ttl: int = 3600):
        self.cache_dir = Path(cache_dir or os.path.join(
            os.path.dirname(__file__), "..", "data", "cache"
        ))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

    def _key_to_path(self, prefix: str, key: str) -> Path:
        h = hashlib.md5(key.encode()).hexdigest()[:12]
        return self.cache_dir / f"{prefix}_{h}.json"

    def get(self, prefix: str, key: str, ttl: int = None) -> Optional[dict]:
        path = self._key_to_path(prefix, key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            age = time.time() - data.get("cached_at", 0)
            if age > (ttl or self.default_ttl):
                return None
            logger.info(f"Cache HIT: {prefix}/{key[:40]}")
            return data["value"]
        except (json.JSONDecodeError, KeyError):
            return None

    def set(self, prefix: str, key: str, value: dict):
        path = self._key_to_path(prefix, key)
        path.write_text(json.dumps({
            "cached_at": time.time(),
            "key": key[:200],
            "value": value,
        }, ensure_ascii=False, indent=2))
        logger.info(f"Cache SET: {prefix}/{key[:40]}")

    def get_stats(self) -> Dict:
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)
        return {"cache_files": len(files), "total_bytes": total_size}


import hmac
import base64


class ZhihuHackathonClient:
    """知乎黑客松 API 客户端（HMAC-SHA256 签名认证）"""

    def __init__(self, app_key: str = None, app_secret: str = None):
        self.app_key = app_key or os.getenv("ZHIHU_APP_KEY", "")
        self.app_secret = app_secret or os.getenv("ZHIHU_API_KEY", "")
        self.base_url = os.getenv("ZHIHU_BASE_URL", "https://openapi.zhihu.com")
        self.cache = CacheManager()
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Crucible/1.0 (ZhihuHackathon2026)",
        })
        # API call counters
        self._call_counts = {
            "search": 0,
            "hot_list": 0,
            "chat": 0,
        }
        self._daily_limits = {
            "search": 100,
            "hot_list": 100,
            "chat": 100,
        }

    def _check_limit(self, api_name: str) -> bool:
        count = self._call_counts.get(api_name, 0)
        limit = self._daily_limits.get(api_name, 999)
        if count >= limit:
            logger.warning(f"Daily limit reached for {api_name}: {count}/{limit}")
            return False
        return True

    def _increment(self, api_name: str):
        self._call_counts[api_name] = self._call_counts.get(api_name, 0) + 1

    def _sign(self) -> Dict[str, str]:
        """生成 HMAC-SHA256 签名头"""
        ts = str(int(time.time()))
        log_id = f"req_{int(time.time() * 1000000)}"
        extra_info = ""
        sign_str = f"app_key:{self.app_key}|ts:{ts}|logid:{log_id}|extra_info:{extra_info}"
        sig = hmac.new(
            self.app_secret.encode(),
            sign_str.encode(),
            hashlib.sha256,
        ).digest()
        sign = base64.b64encode(sig).decode()
        return {
            "X-App-Key": self.app_key,
            "X-Timestamp": ts,
            "X-Log-Id": log_id,
            "X-Sign": sign,
            "X-Extra-Info": extra_info,
        }

    def _signed_get(self, path: str, params: dict = None, timeout: int = 15) -> requests.Response:
        headers = self._sign()
        return self.session.get(f"{self.base_url}{path}", params=params, headers=headers, timeout=timeout)

    def _signed_post(self, path: str, data: dict = None, timeout: int = 15) -> requests.Response:
        headers = self._sign()
        return self.session.post(f"{self.base_url}{path}", json=data, headers=headers, timeout=timeout)

    # ── 搜索 API ───────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """全站搜索 — 返回文章和问答

        GET /api/v1/content/zhihu_search
        限制: 100次/天
        """
        # Check cache first
        cached = self.cache.get("search", query)
        if cached:
            return [SearchResult(**r) for r in cached]

        if not self._check_limit("search"):
            return []

        try:
            ts = str(int(time.time()))
            headers = {
                "Authorization": f"Bearer {self.app_secret}",
                "X-Request-Timestamp": ts,
            }
            resp = requests.get(
                "https://developer.zhihu.com/api/v1/content/zhihu_search",
                params={"Query": query, "Limit": limit},
                headers=headers,
                timeout=15,
            )
            self._increment("search")

            if resp.ok:
                data = resp.json()
                items = data.get("Data", {}).get("Items", [])
                results = []
                for item in items:
                    results.append(SearchResult(
                        title=item.get("Title", ""),
                        summary=item.get("ContentText", "")[:500],
                        author=item.get("AuthorName", ""),
                        url=item.get("Url", ""),
                        voteup_count=item.get("VoteUpCount", 0),
                        comment_count=item.get("CommentCount", 0),
                        relevance_score=item.get("RankingScore", 0),
                        authority_level=item.get("AuthorityLevel", ""),
                        selected_comments=[c.get("Content","") for c in item.get("CommentInfoList", [])],
                    ))
                # Cache results
                self.cache.set("search", query, [asdict_simple(r) for r in results])
                return results
            else:
                logger.warning(f"Search API returned {resp.status_code}: {resp.text[:200]}")
                return []
        except Exception as e:
            logger.error(f"Search API error: {e}")
            return []

    # ── 热榜 API ───────────────────────────────────────

    def get_hot_list(self, hours: int = 24) -> List[HotItem]:
        """获取热榜

        GET /api/v1/content/hot_list
        限制: 100次/天
        """
        cache_key = f"hot_{hours}h"
        cached = self.cache.get("hot_list", cache_key)
        if cached:
            return [HotItem(**r) for r in cached]

        if not self._check_limit("hot_list"):
            return []

        try:
            ts = str(int(time.time()))
            headers = {
                "Authorization": f"Bearer {self.app_secret}",
                "X-Request-Timestamp": ts,
            }
            resp = requests.get(
                "https://developer.zhihu.com/api/v1/content/hot_list",
                params={"Hours": hours},
                headers=headers,
                timeout=15,
            )
            self._increment("hot_list")

            if resp.ok:
                data = resp.json()
                items = data.get("Data", {}).get("Items", [])
                results = []
                for item in items:
                    results.append(HotItem(
                        title=item.get("Title", ""),
                        hot_score=item.get("HotScore", 0),
                        url=item.get("Url", ""),
                        summary=item.get("Summary", ""),
                        voteup_count=item.get("VoteupCount", 0),
                        comment_count=item.get("CommentCount", 0),
                    ))
                # Cache for longer (hot list changes less frequently)
                self.cache.set("hot_list", cache_key, [asdict_simple(r) for r in results])
                return results
            return []
        except Exception as e:
            logger.error(f"Hot list API error: {e}")
            return []

    # ── 直答 Agent (LLM) ──────────────────────────────

    def chat(self, messages: List[Dict], model: str = "zhida-fast-1p5",
             temperature: float = 0.3, max_tokens: int = 2000, stream: bool = False) -> Optional[str]:
        """调用直答 Agent — 知乎提供的 LLM 接口

        POST https://developer.zhihu.com/v1/chat/completions
        鉴权: Bearer <access_secret> + X-Request-Timestamp
        限制: 100次/天
        模型: zhida-fast-1p5 / zhida-thinking-1p5 / zhida-agent
        """
        # Cache based on input hash
        cache_key = json.dumps(messages, ensure_ascii=False)
        cached = self.cache.get("chat", cache_key)
        if cached:
            return cached.get("content")

        if not self._check_limit("chat"):
            return None

        try:
            ts = str(int(time.time()))
            resp = requests.post(
                "https://developer.zhihu.com/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": stream,
                },
                headers={
                    "Authorization": f"Bearer {self.app_secret}",
                    "X-Request-Timestamp": ts,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            self._increment("chat")

            if resp.ok:
                data = resp.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                content = msg.get("content", "") or msg.get("reasoning_content", "")
                # Cache the result
                self.cache.set("chat", cache_key, {"content": content})
                return content
            else:
                logger.warning(f"Chat API returned {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Chat API error: {e}")
            return None

    # ── 圈子 API ───────────────────────────────────────

    def get_ring_posts(self, ring_id: str, limit: int = 20) -> List[Dict]:
        """获取圈子帖子列表"""
        cached = self.cache.get("ring", f"{ring_id}_{limit}")
        if cached:
            return cached

        try:
            resp = self._signed_get(
                "/openapi/ring/detail",
                params={"ring_id": ring_id, "limit": limit},
            )
            if resp.ok:
                data = resp.json().get("data", [])
                self.cache.set("ring", f"{ring_id}_{limit}", data)
                return data
            return []
        except Exception as e:
            logger.error(f"Ring API error: {e}")
            return []

    def post_pin(self, content: str, ring_id: str = None) -> Optional[Dict]:
        """发布一条想法到圈子"""
        try:
            resp = self._signed_post(
                "/openapi/publish/pin",
                data={"content": content, "ring_id": ring_id},
            )
            if resp.ok:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Post pin error: {e}")
            return None

    def get_comments(self, post_id: str, limit: int = 20) -> List[Dict]:
        """获取评论列表"""
        cached = self.cache.get("comments", post_id)
        if cached:
            return cached
        try:
            resp = self._signed_get(
                "/openapi/comment/list",
                params={"post_id": post_id, "limit": limit},
            )
            if resp.ok:
                data = resp.json().get("data", [])
                self.cache.set("comments", post_id, data)
                return data
            return []
        except Exception as e:
            logger.error(f"Comments API error: {e}")
            return []

    # ── 统计 ───────────────────────────────────────────

    def get_usage_stats(self) -> Dict:
        return {
            "api_calls": dict(self._call_counts),
            "daily_limits": dict(self._daily_limits),
            "remaining": {
                k: self._daily_limits.get(k, 0) - self._call_counts.get(k, 0)
                for k in self._call_counts
            },
            "cache": self.cache.get_stats(),
        }


    # ── DeepSeek（结构化输出专用）──────────────────────

    def deepseek_chat(self, messages: List[Dict], model: str = "deepseek-chat",
                      temperature: float = 0.3, max_tokens: int = 2000) -> Optional[str]:
        """调用 DeepSeek API — 用于结构化 JSON 输出（论点提取、碰撞生成）

        DeepSeek 做结构化输出比知乎直答靠谱得多
        """
        cache_key = f"ds_{json.dumps(messages, ensure_ascii=False)}"
        cached = self.cache.get("deepseek", cache_key)
        if cached:
            return cached.get("content")

        ds_key = os.getenv("DEEPSEEK_API_KEY", "")
        ds_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        if not ds_key:
            return None

        try:
            resp = requests.post(
                f"{ds_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                headers={
                    "Authorization": f"Bearer {ds_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if resp.ok:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                self.cache.set("deepseek", cache_key, {"content": content})
                return content
            else:
                logger.error(f"DeepSeek API error: {resp.status_code} {resp.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"DeepSeek error: {e}")
            return None


def asdict_simple(obj):
    """Simple dataclass to dict"""
    import dataclasses
    if dataclasses.is_dataclass(obj):
        return {k: v for k, v in dataclasses.asdict(obj).items()}
    return obj


# ── Quick test with preloaded data ────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    client = ZhihuHackathonClient()

    # Test search (will fail before 5/12, but shows the interface)
    print("=== Search Test ===")
    results = client.search("AI 取代程序员")
    if results:
        for r in results[:3]:
            print(f"  {r.title} ({r.voteup_count}赞)")
            print(f"    {r.summary[:80]}...")
    else:
        print("  (API not yet available — using mock data)")

    # Test hot list
    print("\n=== Hot List Test ===")
    hot = client.get_hot_list()
    if hot:
        for h in hot[:3]:
            print(f"  🔥 {h.title} (热度 {h.hot_score})")
    else:
        print("  (API not yet available)")

    # Usage stats
    print(f"\n=== Usage Stats ===")
    stats = client.get_usage_stats()
    print(f"  Calls: {stats['api_calls']}")
    print(f"  Cache: {stats['cache']}")
