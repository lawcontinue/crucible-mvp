"""观点提取 + 阵营聚类引擎"""
import json
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from zhihu_api import Answer, Comment, QuestionData

logger = logging.getLogger(__name__)


@dataclass
class Argument:
    """单个论据"""
    content: str           # 论据内容
    strength: str          # "strong" | "weak"
    source_answer_id: str  # 来源回答 ID
    source_author: str     # 来源作者


@dataclass
class Camp:
    """观点阵营"""
    id: str                # 阵营 ID (camp_0, camp_1, ...)
    label: str             # 阵营标签（一句话概括）
    summary: str           # 阵营核心观点（2-3 句）
    stance: str            # "pro" | "con" | "nuanced"
    arguments: List[Argument] = field(default_factory=list)
    supporter_count: int = 0  # 支持者数量（按点赞估算）
    representative_answers: List[str] = field(default_factory=list)  # 代表性回答 ID


@dataclass
class BattleMap:
    """战场地图 — 一个问题的完整观点分析"""
    question_id: str
    question_title: str
    camps: List[Camp] = field(default_factory=list)
    consensus_points: List[str] = field(default_factory=list)     # 双方都同意的
    core_disagreements: List[str] = field(default_factory=list)   # 核心分歧


class OpinionAnalyzer:
    """观点分析器 — 调用知乎直答 Agent 或规则引擎 fallback"""

    def __init__(self, zhihu_client=None):
        """zhihu_client: ZhihuHackathonClient 实例（提供 chat 接口）"""
        self.zhihu_client = zhihu_client

    def analyze(self, question_data: QuestionData, max_camps: int = 4) -> BattleMap:
        """分析一个问题的观点分布"""
        if not question_data.answers:
            return BattleMap(
                question_id=question_data.question_id,
                question_title=question_data.title,
            )

        # 构建分析输入
        answers_text = self._format_answers(question_data.answers[:20])

        # 调用知乎直答 Agent 或用规则引擎 fallback
        if self.zhihu_client:
            result = self._llm_analyze(question_data.title, answers_text, max_camps)
        else:
            result = self._rule_based_analyze(question_data, max_camps)

        return result

    def _format_answers(self, answers: List[Answer], max_chars: int = 8000) -> str:
        """格式化回答列表供 LLM 分析"""
        parts = []
        total = 0
        for a in sorted(answers, key=lambda x: x.voteup_count, reverse=True):
            snippet = a.content[:500]
            entry = f"【{a.author}({a.voteup_count}赞)】{snippet}"
            if total + len(entry) > max_chars:
                break
            parts.append(entry)
            total += len(entry)
        return "\n---\n".join(parts)

    def _llm_analyze(self, title: str, answers_text: str,
                     max_camps: int) -> BattleMap:
        """调用 LLM 做观点分析"""
        prompt = f"""你是一个观点分析专家。请分析以下知乎问题的高赞回答，提取观点阵营。

问题：{title}

高赞回答摘要：
{answers_text}

请按以下 JSON 格式输出（不要输出其他内容）：
{{
  "camps": [
    {{
      "label": "阵营名称（简短）",
      "summary": "核心观点（2-3句）",
      "stance": "pro/con/nuanced",
      "strong_arguments": ["最强论据1", "最强论据2", "最强论据3"],
      "weak_points": ["最弱漏洞1"]
    }}
  ],
  "consensus_points": ["双方都同意的点"],
  "core_disagreements": ["核心分歧点"]
}}

要求：
1. 提取 2-{max_camps} 个观点阵营
2. 每个阵营的论据必须来自真实回答内容，不要编造
3. 强论据是逻辑严密、有数据支撑的；弱漏洞是逻辑跳跃或以偏概全的
4. 共识点 = 不同阵营都承认的事实
5. 分歧点 = 阵营之间根本性对立的地方"""

        try:
            text = self.zhihu_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )
            if text:
                # 解析 JSON
                json_str = text
                if "```json" in text:
                    json_str = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    json_str = text.split("```")[1].split("```")[0]
                data = json.loads(json_str)

                camps = []
                for i, c in enumerate(data.get("camps", [])):
                    args = []
                    for sa in c.get("strong_arguments", [])[:3]:
                        args.append(Argument(
                            content=sa, strength="strong",
                            source_answer_id="", source_author="",
                        ))
                    for wp in c.get("weak_points", [])[:1]:
                        args.append(Argument(
                            content=wp, strength="weak",
                            source_answer_id="", source_author="",
                        ))
                    camps.append(Camp(
                        id=f"camp_{i}",
                        label=c["label"],
                        summary=c["summary"],
                        stance=c.get("stance", "nuanced"),
                        arguments=args,
                    ))

                return BattleMap(
                    question_id="",  # caller fills
                    question_title=title,
                    camps=camps,
                    consensus_points=data.get("consensus_points", []),
                    core_disagreements=data.get("core_disagreements", []),
                )
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")

        # Fallback
        return self._rule_based_analyze_fallback(title, max_camps)

    def _rule_based_analyze(self, question_data: QuestionData,
                            max_camps: int) -> BattleMap:
        """规则引擎 fallback — 当 LLM 不可用时"""
        # 简单按关键词聚类
        pro_keywords = ["应该", "可以", "好处", "优势", "必要", "支持", "有利"]
        con_keywords = ["不该", "不能", "坏处", "劣势", "不必要", "反对", "风险"]

        pro_answers = []
        con_answers = []
        nuanced_answers = []

        for a in question_data.answers[:20]:
            text = a.content
            pro_score = sum(1 for kw in pro_keywords if kw in text)
            con_score = sum(1 for kw in con_keywords if kw in text)
            if pro_score > con_score + 1:
                pro_answers.append(a)
            elif con_score > pro_score + 1:
                con_answers.append(a)
            else:
                nuanced_answers.append(a)

        camps = []
        if pro_answers:
            top = pro_answers[0]
            camps.append(Camp(
                id="camp_0",
                label="支持方",
                summary=f"基于 {len(pro_answers)} 个高赞回答的支持观点",
                stance="pro",
                arguments=[
                    Argument(content=a.content[:200], strength="strong",
                             source_answer_id=a.id, source_author=a.author)
                    for a in pro_answers[:3]
                ],
                supporter_count=sum(a.voteup_count for a in pro_answers),
            ))
        if con_answers:
            top = con_answers[0]
            camps.append(Camp(
                id="camp_1",
                label="反对方",
                summary=f"基于 {len(con_answers)} 个高赞回答的反对观点",
                stance="con",
                arguments=[
                    Argument(content=a.content[:200], strength="strong",
                             source_answer_id=a.id, source_author=a.author)
                    for a in con_answers[:3]
                ],
                supporter_count=sum(a.voteup_count for a in con_answers),
            ))
        if nuanced_answers:
            camps.append(Camp(
                id="camp_2",
                label="中间派",
                summary=f"基于 {len(nuanced_answers)} 个回答的 nuanced 观点",
                stance="nuanced",
                arguments=[
                    Argument(content=a.content[:200], strength="strong",
                             source_answer_id=a.id, source_author=a.author)
                    for a in nuanced_answers[:2]
                ],
                supporter_count=sum(a.voteup_count for a in nuanced_answers),
            ))

        return BattleMap(
            question_id=question_data.question_id,
            question_title=question_data.title,
            camps=camps,
        )

    def _rule_based_analyze_fallback(self, title: str,
                                      max_camps: int) -> BattleMap:
        return BattleMap(
            question_id="",
            question_title=title,
            camps=[
                Camp(id="camp_0", label="待分析", summary="数据加载中", stance="nuanced"),
            ],
        )


@dataclass
class StanceEvent:
    """立场变化事件"""
    camp_id: str           # 选择的阵营
    action: str            # "join" | "hold" | "shift" | "surrender"
    triggered_by: str      # 触发原因（看到了哪个论据）
    timestamp: float = 0


class StanceTracker:
    """立场追踪器"""

    def __init__(self):
        self.events: List[StanceEvent] = []
        self.user_camp: Optional[str] = None
        self.shift_count = 0

    def join_camp(self, camp_id: str):
        self.user_camp = camp_id
        self.events.append(StanceEvent(
            camp_id=camp_id, action="join", triggered_by="initial_choice",
        ))

    def see_opposing_argument(self, camp_id: str, argument: str):
        self.events.append(StanceEvent(
            camp_id=camp_id, action="see_opposing",
            triggered_by=argument[:200],
        ))

    def hold_stance(self):
        self.events.append(StanceEvent(
            camp_id=self.user_camp, action="hold",
            triggered_by="user_decision",
        ))

    def shift_stance(self, new_camp_id: str, reason: str):
        self.shift_count += 1
        old_camp = self.user_camp
        self.user_camp = new_camp_id
        self.events.append(StanceEvent(
            camp_id=new_camp_id, action="shift",
            triggered_by=reason[:200],
        ))

    def surrender(self):
        self.shift_count += 1
        self.events.append(StanceEvent(
            camp_id="none", action="surrender",
            triggered_by="user_surrender",
        ))

    def get_stats(self) -> Dict:
        return {
            "total_events": len(self.events),
            "shifts": self.shift_count,
            "final_stance": self.user_camp,
            "journey": [
                {"action": e.action, "camp": e.camp_id, "trigger": e.triggered_by[:100]}
                for e in self.events
            ],
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from zhihu_api import ZhihuClient

    client = ZhihuClient()
    qid = "19550561"
    data = client.fetch_question_data(qid)
    print(f"Loaded: {data.title} ({len(data.answers)} answers)")

    analyzer = OpinionAnalyzer()
    battle_map = analyzer.analyze(data)
    print(f"\n战场地图: {len(battle_map.camps)} 个阵营")
    for camp in battle_map.camps:
        print(f"  {camp.label}: {camp.summary[:60]}...")
        for arg in camp.arguments[:2]:
            print(f"    [{'强' if arg.strength == 'strong' else '弱'}] {arg.content[:80]}...")
    if battle_map.consensus_points:
        print(f"\n共识点: {battle_map.consensus_points}")
    if battle_map.core_disagreements:
        print(f"核心分歧: {battle_map.core_disagreements}")
