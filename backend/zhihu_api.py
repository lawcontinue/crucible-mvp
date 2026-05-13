"""知乎数据获取层 — API v4 + 页面解析 fallback"""
import os
import re
import json
import time
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class Answer:
    id: str
    author: str
    content: str  # plain text
    voteup_count: int
    comment_count: int
    url: str = ""


@dataclass
class Comment:
    id: str
    author: str
    content: str
    voteup_count: int


@dataclass
class QuestionData:
    question_id: str
    title: str
    detail: str
    answers: List[Answer] = field(default_factory=list)
    comments: Dict[str, List[Comment]] = field(default_factory=dict)  # answer_id -> comments


class ZhihuClient:
    """知乎数据获取客户端，API 优先，页面解析 fallback"""

    BASE_URL = "https://www.zhihu.com/api/v4"
    WEB_URL = "https://www.zhihu.com"

    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id or os.getenv("ZHIHU_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("ZHIHU_CLIENT_SECRET", "")
        self.access_token = ""
        self._token_expires = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MindArena/0.1 (Hackathon Demo)",
            "Accept": "application/json",
        })

    # ── OAuth ──────────────────────────────────────────

    def _ensure_token(self):
        if self.access_token and time.time() < self._token_expires:
            return
        if not self.client_id or not self.client_secret:
            logger.warning("No API credentials, will use fallback")
            return
        try:
            resp = requests.post(
                f"{self.BASE_URL}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                self.access_token = data["access_token"]
                self._token_expires = time.time() + data.get("expires_in", 3600) - 60
                self.session.headers["Authorization"] = f"Bearer {self.access_token}"
                logger.info("Zhihu API token acquired")
            else:
                logger.warning(f"Token request failed: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Token request error: {e}")

    # ── API methods ────────────────────────────────────

    def _api_get(self, path: str, params: dict = None) -> Optional[dict]:
        self._ensure_token()
        if not self.access_token:
            return None
        try:
            resp = self.session.get(
                f"{self.BASE_URL}{path}",
                params=params,
                timeout=15,
            )
            if resp.status_code == 429:
                logger.warning("Rate limited, backing off")
                time.sleep(2)
                return None
            if resp.ok:
                return resp.json()
            logger.warning(f"API {path} returned {resp.status_code}")
            return None
        except Exception as e:
            logger.warning(f"API request error: {e}")
            return None

    def get_question(self, question_id: str) -> Optional[Dict]:
        return self._api_get(f"/questions/{question_id}")

    def get_answers(self, question_id: str, limit: int = 20,
                    offset: int = 0, sort_by: str = "default") -> Optional[Dict]:
        """获取问题下的回答。sort_by: default(综合) | by_votes(按点赞)"""
        return self._api_get(
            f"/questions/{question_id}/answers",
            params={"limit": min(limit, 50), "offset": offset, "sort_by": sort_by},
        )

    def get_comments(self, answer_id: str, limit: int = 20) -> Optional[Dict]:
        return self._api_get(
            f"/answers/{answer_id}/comments",
            params={"limit": min(limit, 50)},
        )

    # ── Fallback: page scraping ────────────────────────

    def _scrape_question(self, question_id: str) -> Optional[QuestionData]:
        """页面解析 fallback — 当 API 不可用时"""
        url = f"{self.WEB_URL}/question/{question_id}"
        try:
            resp = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
            }, timeout=15)
            if not resp.ok:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            # 提取标题
            title_el = soup.select_one("h1.QuestionHeader-title")
            title = title_el.get_text(strip=True) if title_el else f"Question {question_id}"

            # 提取详情
            detail_el = soup.select_one(".QuestionHeader-detail span.RichText")
            detail = detail_el.get_text(strip=True) if detail_el else ""

            # 提取初始数据（知乎在页面中嵌入 JSON）
            answers = []
            init_data = re.search(
                r'"initialState"\s*:\s*(\{.*?\})\s*,\s*"initialFeedInfo"',
                resp.text,
            )
            if init_data:
                try:
                    data = json.loads(init_data.group(1))
                    q_data = data.get("entities", {}).get("questions", {})
                    a_data = data.get("entities", {}).get("answers", {})
                    for aid, a in a_data.items():
                        content_el = BeautifulSoup(a.get("content", ""), "html.parser")
                        author = a.get("author", {}).get("name", "匿名")
                        answers.append(Answer(
                            id=str(aid),
                            author=author,
                            content=content_el.get_text(strip=True)[:2000],
                            voteup_count=a.get("voteupCount", 0),
                            comment_count=a.get("commentCount", 0),
                            url=f"{self.WEB_URL}/question/{question_id}/answer/{aid}",
                        ))
                except json.JSONDecodeError:
                    pass

            logger.info(f"Scraped {len(answers)} answers from page")
            return QuestionData(
                question_id=question_id,
                title=title,
                detail=detail,
                answers=sorted(answers, key=lambda a: a.voteup_count, reverse=True),
            )
        except Exception as e:
            logger.error(f"Scrape error: {e}")
            return None

    # ── Unified interface ──────────────────────────────

    def fetch_question_data(self, question_id: str,
                            max_answers: int = 30) -> QuestionData:
        """统一接口：API 优先，页面解析 fallback，最后用预置数据"""
        # Try 1: API
        if self.access_token or (self.client_id and self.client_secret):
            self._ensure_token()
            q_info = self.get_question(question_id)
            if q_info:
                title = q_info.get("title", "")
                detail = q_info.get("detail", "")
                answers = []
                offset = 0
                while len(answers) < max_answers:
                    data = self.get_answers(
                        question_id, limit=20, offset=offset, sort_by="by_votes",
                    )
                    if not data or not data.get("data"):
                        break
                    for a in data["data"]:
                        content_el = BeautifulSoup(a.get("content", ""), "html.parser")
                        answers.append(Answer(
                            id=str(a["id"]),
                            author=a.get("author", {}).get("name", "匿名"),
                            content=content_el.get_text(strip=True)[:2000],
                            voteup_count=a.get("voteup_count", 0),
                            comment_count=a.get("comment_count", 0),
                            url=a.get("url", ""),
                        ))
                    paging = data.get("paging", {})
                    if not paging.get("is_end") is False:
                        break
                    offset += 20
                    time.sleep(0.5)  # rate limit

                logger.info(f"API: got {len(answers)} answers for Q{question_id}")
                return QuestionData(
                    question_id=question_id, title=title, detail=detail,
                    answers=answers,
                )

        # Try 2: page scraping
        result = self._scrape_question(question_id)
        if result and result.answers:
            return result

        # Try 3: preloaded data
        return self._load_preloaded(question_id)

    def _load_preloaded(self, question_id: str) -> QuestionData:
        """加载预置数据包"""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        filepath = os.path.join(data_dir, f"{question_id}.json")
        if os.path.exists(filepath):
            with open(filepath) as f:
                data = json.load(f)
            logger.info(f"Loaded preloaded data for Q{question_id}")
            return QuestionData(
                question_id=data["question_id"],
                title=data["title"],
                detail=data.get("detail", ""),
                answers=[Answer(**a) for a in data.get("answers", [])],
            )

        logger.warning(f"No data available for Q{question_id}")
        return QuestionData(
            question_id=question_id,
            title=f"Question {question_id}",
            detail="数据暂不可用",
        )

    @staticmethod
    def extract_question_id(url_or_id: str) -> str:
        """从 URL 或纯 ID 中提取问题 ID"""
        if url_or_id.isdigit():
            return url_or_id
        m = re.search(r"question/(\d+)", url_or_id)
        if m:
            return m.group(1)
        return url_or_id


# ── Quick test ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = ZhihuClient()  # no credentials → uses fallback
    # Test with a popular question
    qid = "19550561"  # "如何优雅地使用知乎"
    data = client.fetch_question_data(qid)
    print(f"Question: {data.title}")
    print(f"Answers: {len(data.answers)}")
    if data.answers:
        top = data.answers[0]
        print(f"Top answer by {top.author} ({top.voteup_count} votes):")
        print(f"  {top.content[:200]}...")
