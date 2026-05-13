from pathlib import Path
"""熔炉引擎 — 争议话题碰撞核心

输入一个争议话题 → 从知乎真实回答中抽取论点 + AI 苏格拉底式再加工（3轮碰撞）
Fallback: 使用预置 mock 数据
"""
import json
import uuid
import time
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── 预置争议话题 ──────────────────────────────────────

PRESET_TOPICS = [
    {
        "id": "topic_01",
        "title": "AI 会不会取代程序员？",
        "description": "AI 代码生成能力飞速提升，程序员的未来在哪里？",
        "tags": ["AI", "职业", "技术"],
        "pro_label": "AI 会取代大部分程序员",
        "con_label": "AI 无法取代程序员核心价值",
        "mock_rounds": {
            "1": {
                "pro": "AI 已经能生成完整功能模块，Copilot 让编码效率提升 55%。当 AI 能写 90% 的代码时，剩下的 10% 真的需要人类吗？GitHub 报告显示，采用 AI 辅助的团队项目交付速度提高了 40%。",
                "con": "编程的核心不是写代码，而是理解需求、设计架构、处理边界条件。AI 擅长模式匹配，但不擅长理解'为什么需要这个功能'。一个不理解业务上下文的代码生成器，产出的代码越多，技术债越重。",
            },
            "2": {
                "pro": "你说得对，理解需求很重要。但如果从产品经理角度看——当 AI 能从自然语言描述直接生成可运行的原型，'理解需求'这件事本身是不是也可以被拆解？需求分析本质上也是模式匹配：用户说 X，历史上 80% 的案例意味着 Y。",
                "con": "这个判断的数据基础是什么？自然语言到代码的准确率在真实项目中不到 60%。你说的'模式匹配'忽略了需求中的隐性知识——客户说不出来的东西。而且，当系统出故障时，谁去排查？谁在凌晨 3 点上线修复？AI 能生成代码，但不能承担责任。",
            },
            "3": {
                "pro": "我承认'承担责任'这一点暂时无法替代。但回到核心：我们不讨论 AI 是否取代 100% 的程序员，而是 80%。剩余 20% 做的是今天架构师的工作。历史告诉我们，每次技术革命淘汰的是'执行层'，创造的是'决策层'。问题是：现在的程序员有多少在做真正的'决策'？",
                "con": "我修正一下立场：AI 确实会取代大量重复性编码工作，这是好事。但'程序员'的定义会进化，不是消失。就像计算器没有取代数学家，只是让他们专注于更高层次的问题。未来的程序员更像是'AI 编排师'——但这个角色的门槛，可能比现在的编程更高，而不是更低。",
            },
        },
    },
    {
        "id": "topic_02",
        "title": "远程办公是不是未来的唯一方向？",
        "description": "疫情后远程办公成为主流趋势，但它真的是最优解吗？",
        "tags": ["工作方式", "管理", "效率"],
        "pro_label": "远程办公是必然趋势",
        "con_label": "线下办公有不可替代的价值",
        "mock_rounds": {
            "1": {
                "pro": "Stanford 研究显示远程工作者效率提升 13%，离职率降低 50%。员工省下每天 2 小时通勤时间，企业省下 30% 办公成本。这是双赢。",
                "con": "效率提升的数据来自短期研究，长期效果呢？微软的 Work Trend Index 显示远程团队的创新提案减少 40%，跨部门协作减少 25%。效率和创新是两件事。",
            },
            "2": {
                "pro": "如果从全球人才竞争的角度看——远程办公让小公司也能招到硅谷级别的人才。地理位置不再是壁垒，这意味着更公平的竞争环境。创新减少可能只是过渡期的问题，工具和流程在进化。",
                "con": "你说'工具在进化'，但 FaceTime 研究表明，视频会议中非语言信息丢失 60%。创造力往往来自走廊里的偶遇、白板前的争论、午餐时的闲聊。这些不是工具能复制的。你觉得 Slack 能替代这些吗？",
            },
            "3": {
                "pro": "我承认自发交流确实受损。但解决方案不是回办公室，而是混合模式：远程为主 + 定期线下聚集（每月 1-2 次）。这样既保留效率，又不完全丢失人际连接。纯远程和纯线下都是极端。",
                "con": "混合模式其实是我的立场。但关键问题是：谁来决定哪些天来办公室？如果管理层来，又回到了信任问题。我见过最好的做法是：团队自组织。不过，这要求很高的团队成熟度，大多数公司做不到。",
            },
        },
    },
    {
        "id": "topic_03",
        "title": "学历贬值是事实还是错觉？",
        "description": "硕博遍地走，本科不如狗，学历真的不值钱了吗？",
        "tags": ["教育", "社会", "就业"],
        "pro_label": "学历正在加速贬值",
        "con_label": "学历价值在转型而非贬值",
        "mock_rounds": {
            "1": {
                "pro": "2025 年高校毕业生 1187 万，研究生 130 万。供给量翻了 5 倍，需求端没有等比例增长。经济学 101：供大于求，价格下降。学历的'价格'就是起薪——过去十年本科起薪实际购买力下降了 30%。",
                "con": "你混淆了'学历的绝对价值'和'学历的相对优势'。学历确实不再是稀缺信号，但它仍然是能力筛选的最廉价工具。没有学历的求职者，简历通过率比有学历的低 60%。贬值的是'学历溢价'，不是学历本身。",
            },
            "2": {
                "pro": "如果从雇主角度看——越来越多大厂取消学历要求，Google、Apple、IBM 已经不看学历了。当头部企业都不再需要这个信号时，它的筛选价值还在吗？你的'最廉价工具'论点，建立在过去的数据上。",
                "con": "这个判断需要区分'头部企业'和'整体市场'。取消学历要求的 5 家公司不代表 500 万家企业。而且这些公司的筛选成本转嫁到了技术面试上——面试 1000 人选出 10 人的成本，谁在承担？中小公司付不起这个成本，学历筛选对他们仍然是最优解。",
            },
            "3": {
                "pro": "我承认短期学历仍有筛选价值。但趋势很明确：能力证明正在多元化（GitHub、作品集、证书）。学历从'硬通货'变成'入场券之一'。未来 10 年，这个趋势只会加速。不是学历没用，而是只有学历不够了。",
                "con": "实际上我们达成共识了：学历的相对价值在下降，但它仍然是社会流动的基础设施。问题不在学历本身，在于我们花了 4 年拿学历的同时，有没有积累其他能力证明。贬值的是'只靠学历'的策略。",
            },
        },
    },
    {
        "id": "topic_04",
        "title": "应该对所有 AI 生成内容强制标注吗？",
        "description": "AI 生成内容越来越多，用户有权知道吗？",
        "tags": ["AI", "法律", "内容"],
        "pro_label": "必须强制标注 AI 生成内容",
        "con_label": "强制标注不现实且有害",
        "mock_rounds": {
            "1": {
                "pro": "欧盟 AI Act 已经要求 AI 生成内容必须标注。中国《标识办法》2025年9月实施。用户有知情权——看到一篇文章，有权知道是人写的还是 AI 生成的。这不是限制，是透明度。",
                "con": "标注的技术实现几乎不可能。AI 辅助写作（Grammarly、自动补全）算不算 AI 生成？人工写 70% + AI 润色 30% 怎么标？非黑即白的'AI/非AI'分类不符合现实。而且标注会制造信任鸿沟——标了 AI 的内容，质量再好也会被歧视。",
            },
            "2": {
                "pro": "你说'技术不可能'，但水印技术已经在发展。从消费者权益角度看——如果我在知乎看了一篇'亲身经历'，结果发现是 AI 编的，这算不算欺诈？标注不是对质量的判断，是对来源的诚实。你的'信任鸿沟'论点，恰恰说明用户确实在乎来源。",
                "con": "如果从内容质量的角度看——一篇 AI 辅助产出的高质量分析，和一篇人工写的低质水文，谁更应该被标记？强制标注把焦点从'内容质量'转移到'生产方式'上，这是本末倒置。我们应该惩罚低质量内容，而不是某种生产方式。",
            },
            "3": {
                "pro": "我接受你的批评——二元的'AI/非AI'标注确实太粗糙。但我坚持：在特定领域（新闻、医疗、法律建议），AI 生成内容必须标注。这些领域的信息误导后果严重。通用内容可以用分级标注：纯AI、AI辅助、人工为主。不是一刀切。",
                "con": "分级标注是更合理的方向。但我担心执行成本——谁来审核标注的准确性？如果靠自觉，有多少人会主动标'纯AI'？最终可能变成：诚实的人标注，不诚实的人不标注，反而惩罚了诚实者。政策设计必须考虑激励相容。",
            },
        },
    },
    {
        "id": "topic_05",
        "title": "全民基本收入（UBI）在中国可行吗？",
        "description": "AI 取代大量工作后，UBI 是解药还是乌托邦？",
        "tags": ["经济", "AI", "社会政策"],
        "pro_label": "中国应该试点 UBI",
        "con_label": "UBI 在中国不可行",
        "mock_rounds": {
            "1": {
                "pro": "芬兰 UBI 实验显示，领取者心理健康改善 20%，就业率未下降。AI 替代工作不可逆转，与其培训所有人做不存在的岗位，不如保障基本生活尊严。中国财政有能力——2025 年税收 20 万亿，每人每月 1000 元 UBI 约需 16.8 万亿，可通过税制改革实现。",
                "con": "16.8 万亿占税收 84%，这个算术你觉得合理吗？而且芬兰实验样本只有 2000 人，GDP 人均是中国的 3 倍。数据基础完全不同。中国 14 亿人的 UBI，在任何现有财政框架下都是天文数字。",
            },
            "2": {
                "pro": "如果从'渐进式'角度看——不需要一步到位全民 1000 元。可以先从 AI 替代最严重的行业开始，比如制造业工人。而且 UBI 可以替代部分现有福利（低保、失业金），不是纯增量。浙江、深圳有条件做局部试点。",
                "con": "你说'替代现有福利'——这正是 UBI 最大的政治风险。美国多次 UBI 提案被否，原因就是它会替代而非补充现有福利网络。中国的低保体系虽然不完善，但它有针对性。UBI 给马云也发 1000 元，这是资源浪费还是社会共识？",
            },
            "3": {
                "pro": "我承认财政规模是硬约束。但我修正方案：不是全民 UBI，而是'AI 替代补偿金'——针对因 AI 失业的群体，金额与被替代工资挂钩，有期限（如 2 年）。这比 UBI 更精准，财政可承受。核心诉求不变：技术进步的代价不能只让劳动者承担。",
                "con": "你的修正让方案变得合理多了。'AI 替代补偿'本质上是升级版失业保险，这在政策上是可行的。但定义'因 AI 失业'本身就很困难——怎么证明是 AI 替代而不是正常淘汰？这需要一个独立的评估机制。我们可能需要一个'AI 影响评估委员会'。",
            },
        },
    },
]


# ── Data Models ──────────────────────────────────────

@dataclass
class ClashRound:
    """碰撞轮次"""
    round_number: int
    pro_argument: str    # 正方论点
    con_argument: str    # 反方论点
    source_authors: List[str] = field(default_factory=list)  # 论点来源作者


@dataclass
class ClashRecord:
    """碰撞记录"""
    crash_id: str
    topic_id: str
    topic_title: str
    rounds: List[ClashRound] = field(default_factory=list)
    initial_stance: Optional[str] = None  # 用户初始立场
    final_stance: Optional[str] = None    # 用户最终立场
    verdict: Optional[Dict] = None        # 用户评判
    created_at: float = 0
    published: bool = False
    user_id: Optional[str] = None  # 知乎 uid（OAuth 登录后关联）


@dataclass
class VerdictRequest:
    """用户评判"""
    crash_id: str
    winner: str           # "pro" | "con" | "tie" | "both_changed"
    initial_stance: str   # "pro" | "con" | "neutral" | "undecided"
    final_stance: str     # "pro" | "con" | "neutral" | "undecided"
    mind_changed: bool
    comment: str = ""


# ── 苏格拉底式 Prompt 模板 ─────────────────────────────

STYLE_GUIDE = (
    "苏格拉底式追问：不说'你错了'，说'如果从X角度看呢？'"
    "'这个判断的数据基础是什么？'"
)

ROUND1_SYSTEM = """你是一位深谙苏格拉底式辩论的分析师。你的任务是基于真实回答中提取的论点，
组织成最有说服力的正反方开场论点。

要求：
1. 论点必须引用真实回答中的具体观点和数据
2. 每个论点标注来源作者（用【作者名】标记）
3. 不要编造数据，只用提供的素材
4. 风格：{style}"""

ROUND2_SYSTEM = """你是一位深谙苏格拉底式辩论的分析师。现在进入反驳轮。

要求：
1. 先承认对方有力的点（"你说得对，X 确实..."）
2. 然后用"如果从Y角度看呢？"的方式提出新视角
3. 反驳必须引用真实回答中的观点作为支撑
4. 风格：{style}"""

ROUND3_SYSTEM = """你是一位深谙苏格拉底式辩论的分析师。最终轮：修正立场，找共识。

要求：
1. "我承认X这一点"
2. "我修正我的立场为..."
3. 找到可能的共识点
4. 仍然引用真实回答中的观点
5. 风格：{style}"""


class CrucibleEngine:
    """熔炉引擎 — 争议话题碰撞核心"""

    def __init__(self, zhihu_client=None):
        self.zhihu_client = zhihu_client
        self._cache: Dict[str, ClashRecord] = {}
        self._hot_topics_cache: Optional[List[Dict]] = None
        self._hot_topics_cache_time: float = 0
        self._data_file = Path(__file__).parent.parent / "data" / "crash_records.json"
        self._load_records()

    def _load_records(self):
        """Load crash records from JSON file"""
        try:
            if self._data_file.exists():
                data = json.loads(self._data_file.read_text())
                for item in data:
                    r = ClashRecord(
                        crash_id=item["crash_id"],
                        topic_id=item.get("topic_id", ""),
                        topic_title=item["topic_title"],
                        initial_stance=item.get("initial_stance"),
                        final_stance=item.get("final_stance"),
                        created_at=item.get("created_at", 0),
                        published=item.get("published", False),
                        user_id=item.get("user_id"),
                    )
                    for rd in item.get("rounds", []):
                        r.rounds.append(ClashRound(
                            round_number=rd["round"],
                            pro_argument=rd["pro"],
                            con_argument=rd["con"],
                            source_authors=rd.get("source_authors", []),
                        ))
                    r.verdict = item.get("verdict")
                    self._cache[r.crash_id] = r
                logger.info(f"Loaded {len(self._cache)} crash records from file")
        except Exception as e:
            logger.error(f"Failed to load crash records: {e}")

    def _save_records(self):
        """Save crash records to JSON file"""
        try:
            self._data_file.parent.mkdir(parents=True, exist_ok=True)
            data = []
            for r in self._cache.values():
                data.append({
                    "crash_id": r.crash_id,
                    "topic_id": r.topic_id,
                    "topic_title": r.topic_title,
                    "initial_stance": r.initial_stance,
                    "final_stance": r.final_stance,
                    "created_at": r.created_at,
                    "published": r.published,
                    "user_id": r.user_id,
                    "verdict": r.verdict,
                    "rounds": [{"round": rd.round_number, "pro": rd.pro_argument, "con": rd.con_argument, "source_authors": rd.source_authors} for rd in r.rounds],
                })
            self._data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Failed to save crash records: {e}")


    def _load_records(self):
        """Load crash records from JSON file"""
        try:
            if self._data_file.exists():
                data = json.loads(self._data_file.read_text())
                for item in data:
                    r = ClashRecord(
                        crash_id=item["crash_id"],
                        topic_id=item.get("topic_id", ""),
                        topic_title=item["topic_title"],
                        initial_stance=item.get("initial_stance"),
                        final_stance=item.get("final_stance"),
                        created_at=item.get("created_at", 0),
                        published=item.get("published", False),
                        user_id=item.get("user_id"),
                    )
                    for rd in item.get("rounds", []):
                        r.rounds.append(ClashRound(
                            round_number=rd["round"],
                            pro_argument=rd["pro"],
                            con_argument=rd["con"],
                            source_authors=rd.get("source_authors", []),
                        ))
                    r.verdict = item.get("verdict")
                    self._cache[r.crash_id] = r
                logger.info(f"Loaded {len(self._cache)} crash records from file")
        except Exception as e:
            logger.error(f"Failed to load crash records: {e}")

    def _save_records(self):
        """Save crash records to JSON file"""
        try:
            self._data_file.parent.mkdir(parents=True, exist_ok=True)
            data = []
            for r in self._cache.values():
                data.append({
                    "crash_id": r.crash_id,
                    "topic_id": r.topic_id,
                    "topic_title": r.topic_title,
                    "initial_stance": r.initial_stance,
                    "final_stance": r.final_stance,
                    "created_at": r.created_at,
                    "published": r.published,
                    "user_id": r.user_id,
                    "verdict": r.verdict,
                    "rounds": [{"round": rd.round_number, "pro": rd.pro_argument, "con": rd.con_argument, "source_authors": rd.source_authors} for rd in r.rounds],
                })
            self._data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Failed to save crash records: {e}")

    def get_topics(self) -> List[Dict]:
        """获取争议话题列表（热榜 + 预置）"""
        # 先尝试从热榜获取争议话题
        hot_topics = self._fetch_hot_topics()
        if hot_topics:
            return hot_topics + self._preset_topic_list()

        # Fallback: 只有预置话题
        return self._preset_topic_list()

    def _preset_topic_list(self) -> List[Dict]:
        """从 PRESET_TOPICS 生成话题列表"""
        topics = []
        for t in PRESET_TOPICS:
            topics.append({
                "id": t["id"],
                "title": t["title"],
                "description": t["description"],
                "tags": t["tags"],
                "pro_label": t["pro_label"],
                "con_label": t["con_label"],
            })
        return topics

    def start_crash(self, topic_id: str, initial_stance: str = "undecided", user_id: str = None) -> Dict:
        """开始一场碰撞"""
        topic = self._find_topic(topic_id)
        if not topic:
            return {"error": "Topic not found"}

        crash_id = f"crash_{uuid.uuid4().hex[:8]}"
        record = ClashRecord(
            crash_id=crash_id,
            topic_id=topic_id,
            topic_title=topic["title"],
            initial_stance=initial_stance,
            created_at=time.time(),
            user_id=user_id,
        )

        # Generate rounds (real or mock)
        rounds = self._generate_rounds(topic)
        record.rounds = rounds
        self._cache[crash_id] = record
        self._save_records()

        return {
            "crash_id": crash_id,
            "topic_title": topic["title"],
            "pro_label": topic["pro_label"],
            "con_label": topic["con_label"],
            "total_rounds": len(rounds),
            "initial_stance": initial_stance,
        }

    def get_round(self, crash_id: str, round_number: int) -> Dict:
        """获取第N轮碰撞内容"""
        record = self._cache.get(crash_id)
        if not record:
            return {"error": "Crash not found"}

        for r in record.rounds:
            if r.round_number == round_number:
                result = {
                    "crash_id": crash_id,
                    "round": r.round_number,
                    "pro_argument": r.pro_argument,
                    "con_argument": r.con_argument,
                    "is_final": r.round_number == len(record.rounds),
                }
                if r.source_authors:
                    result["source_authors"] = r.source_authors
                return result

        return {"error": f"Round {round_number} not found"}

    def submit_verdict(self, verdict: VerdictRequest) -> Dict:
        """提交用户评判"""
        record = self._cache.get(verdict.crash_id)
        if not record:
            return {"error": "Crash not found"}

        record.final_stance = verdict.final_stance
        record.verdict = {
            "winner": verdict.winner,
            "initial_stance": verdict.initial_stance,
            "final_stance": verdict.final_stance,
            "mind_changed": verdict.mind_changed,
            "comment": verdict.comment,
        }

        self._save_records()
        return {
            "crash_id": verdict.crash_id,
            "stance_shift": verdict.initial_stance != verdict.final_stance,
            "mind_changed": verdict.mind_changed,
            "message": self._verdict_message(verdict),
            "before_after": {
                "initial_stance": verdict.initial_stance,
                "final_stance": verdict.final_stance,
            },
        }

    def get_record(self, crash_id: str) -> Dict:
        """获取碰撞记录"""
        record = self._cache.get(crash_id)
        if not record:
            return {"error": "Crash not found"}

        return {
            "crash_id": record.crash_id,
            "topic_title": record.topic_title,
            "rounds": [
                {
                    "round": r.round_number,
                    "pro_argument": r.pro_argument,
                    "con_argument": r.con_argument,
                    "source_authors": r.source_authors,
                }
                for r in record.rounds
            ],
            "before_after": {
                "initial_stance": record.initial_stance,
                "final_stance": record.final_stance,
            },
            "verdict": record.verdict,
            "created_at": record.created_at,
            "published": record.published,
        }

    def mark_published(self, crash_id: str) -> Dict:
        """标记已发布"""
        record = self._cache.get(crash_id)
        if not record:
            return {"error": "Crash not found"}
        record.published = True
        self._save_records()
        return {"crash_id": crash_id, "published": True}

    # ── 核心生成流程 ──────────────────────────────────

    def _generate_rounds(self, topic: Dict) -> List[ClashRound]:
        """生成碰撞轮次 — 优先从真实回答中抽取论点"""
        if self.zhihu_client:
            # Step 1: 搜索真实回答
            real_answers = self._search_answers(topic['title'])

            if real_answers:
                # Step 2: 提取论点
                extracted = self._extract_arguments(topic, real_answers)
                if extracted:
                    # Step 3: 基于真实论点生成 3 轮碰撞
                    rounds = self._llm_rounds_from_real(topic, extracted)
                    if rounds:
                        return rounds

            # 尝试纯 LLM 生成（无真实回答时）
            try:
                rounds = self._llm_rounds_fallback(topic)
                if rounds:
                    return rounds
            except Exception as e:
                logger.error(f"LLM fallback generation failed: {e}")

        # Fallback: mock 数据
        return self._get_mock_rounds(topic)

    def _search_answers(self, query: str) -> List[Dict]:
        """搜索知乎真实回答

        调用 zhihu_client.search，按点赞数排序取 top 10
        结果已由 zhihu_hackathon_api.CacheManager 缓存
        """
        if not self.zhihu_client:
            return []

        try:
            results = self.zhihu_client.search(query, limit=15)
            if not results:
                return []

            # 转换为统一 dict 格式，按点赞排序取 top 10
            answers = []
            for r in results:
                answers.append({
                    "title": r.title,
                    "summary": r.summary,
                    "author": r.author,
                    "voteup_count": r.voteup_count,
                    "url": r.url,
                })

            answers.sort(key=lambda x: x["voteup_count"], reverse=True)
            return answers[:10]

        except Exception as e:
            logger.error(f"Search answers failed: {e}")
            return []

    def _extract_arguments(self, topic: Dict, answers: List[Dict]) -> Optional[Dict]:
        """从真实回答中提取正反方论点

        用直答 Agent 做论点提取和聚类
        输出: {"pro_args": [...], "con_args": [...], "consensus": [...]}
        每个论点: {content, source_author, source_snippet}
        """
        if not self.zhihu_client:
            return None

        # 构造回答摘要文本
        answer_texts = []
        for i, a in enumerate(answers[:10], 1):
            answer_texts.append(
                f"【回答{i}】作者：{a['author']}（{a['voteup_count']}赞）\n"
                f"标题：{a['title']}\n"
                f"摘要：{a['summary']}"
            )

        answers_block = "\n\n".join(answer_texts)

        prompt = f"""分析以下知乎真实回答，提取正方和反方的核心论点。

话题：{topic['title']}
正方立场：{topic['pro_label']}
反方立场：{topic['con_label']}

以下是知乎用户的真实回答：

{answers_block}

请严格按以下 JSON 格式输出（不要输出其他内容）：
{{
  "pro_args": [
    {{"content": "论点内容", "source_author": "来源作者名", "source_snippet": "原文关键片段"}}
  ],
  "con_args": [
    {{"content": "论点内容", "source_author": "来源作者名", "source_snippet": "原文关键片段"}}
  ],
  "consensus": [
    {{"content": "共识点", "source_author": "来源作者名"}}
  ]
}}

要求：
1. 每个论点必须来自真实回答，标注来源作者
2. 正方论点支持"{topic['pro_label']}"
3. 反方论点支持"{topic['con_label']}"
4. 提取 3-5 个最强正方论点和 3-5 个最强反方论点
5. 找出双方可能达成的共识点"""

        try:
            text = self.zhihu_client.deepseek_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )
            if not text:
                return None

            # Parse JSON
            json_str = text
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            # 验证结构
            if "pro_args" in data and "con_args" in data:
                return data

            return None

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Extract arguments failed: {e}")
            return None

    def _llm_rounds_from_real(self, topic: Dict, extracted: Dict) -> Optional[List[ClashRound]]:
        """基于真实论点生成 3 轮苏格拉底式碰撞"""
        if not self.zhihu_client:
            return None

        # 构造论点摘要
        pro_args = extracted.get("pro_args", [])
        con_args = extracted.get("con_args", [])
        consensus = extracted.get("consensus", [])

        def format_args(args):
            return "\n".join(
                f"- {a['content']}（来自【{a.get('source_author', '未知')}】: {a.get('source_snippet', '')}）"
                for a in args
            )

        pro_text = format_args(pro_args)
        con_text = format_args(con_args)
        consensus_text = format_args(consensus) if consensus else "暂无"

        all_authors = list(set(
            [a.get("source_author", "") for a in pro_args + con_args]
            + [a.get("source_author", "") for a in consensus]
        ))
        all_authors = [a for a in all_authors if a]

        rounds: List[ClashRound] = []

        try:
            # ── Round 1: 基于真实论点的最强论点 ──
            r1_prompt = f"""以下是来自知乎真实回答的论点：

正方论点：
{pro_text}

反方论点：
{con_text}

共识点：
{consensus_text}

请基于以上真实论点，分别组织正方和反方的最强开场论点（各2-3句话）。
要求引用真实回答中的数据/观点，用【作者名】标注来源。

请严格按以下 JSON 格式输出：
{{"pro": "正方论点", "con": "反方论点"}}"""

            r1_text = self.zhihu_client.deepseek_chat(
                messages=[
                    {"role": "system", "content": ROUND1_SYSTEM.format(style=STYLE_GUIDE)},
                    {"role": "user", "content": r1_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            if r1_text:
                r1_data = self._parse_json_response(r1_text)
                if r1_data:
                    rounds.append(ClashRound(
                        round_number=1,
                        pro_argument=r1_data["pro"],
                        con_argument=r1_data["con"],
                        source_authors=all_authors,
                    ))

            # ── Round 2: 反驳对方 ──
            if rounds:
                r2_prompt = f"""上一轮论点：
正方：{rounds[0].pro_argument}
反方：{rounds[0].con_argument}

真实论点素材：
正方论点：{pro_text}
反方论点：{con_text}

现在请各自反驳对方。先承认对方有力的点，再用新视角质疑。
必须引用真实回答中的观点作为支撑。

请严格按以下 JSON 格式输出：
{{"pro": "正方反驳", "con": "反方反驳"}}"""

                r2_text = self.zhihu_client.deepseek_chat(
                    messages=[
                        {"role": "system", "content": ROUND2_SYSTEM.format(style=STYLE_GUIDE)},
                        {"role": "user", "content": r2_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=1500,
                )
                if r2_text:
                    r2_data = self._parse_json_response(r2_text)
                    if r2_data:
                        rounds.append(ClashRound(
                            round_number=2,
                            pro_argument=r2_data["pro"],
                            con_argument=r2_data["con"],
                            source_authors=all_authors,
                        ))

            # ── Round 3: 修正立场，找共识 ──
            if len(rounds) >= 2:
                r3_prompt = f"""前两轮论点：
Round 1 正方：{rounds[0].pro_argument}
Round 1 反方：{rounds[0].con_argument}
Round 2 正方：{rounds[1].pro_argument}
Round 2 反方：{rounds[1].con_argument}

共识素材：{consensus_text}

最终轮：请各自修正立场，找到共识点。承认对方有理的部分。
仍然引用真实回答中的观点。

请严格按以下 JSON 格式输出：
{{"pro": "正方最终立场", "con": "反方最终立场"}}"""

                r3_text = self.zhihu_client.deepseek_chat(
                    messages=[
                        {"role": "system", "content": ROUND3_SYSTEM.format(style=STYLE_GUIDE)},
                        {"role": "user", "content": r3_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=1500,
                )
                if r3_text:
                    r3_data = self._parse_json_response(r3_text)
                    if r3_data:
                        rounds.append(ClashRound(
                            round_number=3,
                            pro_argument=r3_data["pro"],
                            con_argument=r3_data["con"],
                            source_authors=all_authors,
                        ))

            return rounds if len(rounds) == 3 else (rounds if rounds else None)

        except Exception as e:
            logger.error(f"LLM rounds from real failed: {e}")
            return rounds if rounds else None

    def _llm_rounds_fallback(self, topic: Dict) -> Optional[List[ClashRound]]:
        """纯 LLM 生成碰撞（无真实回答时的降级方案）"""
        if not self.zhihu_client:
            return None

        rounds = []
        try:
            # Round 1
            r1_prompt = f"""请为以下争议话题分别给出最强论点。

话题：{topic['title']}
正方立场：{topic['pro_label']}
反方立场：{topic['con_label']}

风格要求：{STYLE_GUIDE}

请严格按以下 JSON 格式输出：
{{"pro": "正方论点（2-3句话，有数据支撑）", "con": "反方论点（2-3句话，有数据支撑）"}}"""

            r1_text = self.zhihu_client.deepseek_chat(
                messages=[{"role": "user", "content": r1_prompt}],
                temperature=0.7,
                max_tokens=1500,
            )
            if r1_text:
                r1_data = self._parse_json_response(r1_text)
                if r1_data:
                    rounds.append(ClashRound(
                        round_number=1,
                        pro_argument=r1_data["pro"],
                        con_argument=r1_data["con"],
                    ))

            # Round 2
            if rounds:
                r2_prompt = f"""上一轮论点：
正方：{rounds[0].pro_argument}
反方：{rounds[0].con_argument}

现在请各自反驳对方。先承认对方有力的点，再提出新视角。
风格要求：{STYLE_GUIDE}

请严格按以下 JSON 格式输出：
{{"pro": "正方反驳（2-3句）", "con": "反方反驳（2-3句）"}}"""

                r2_text = self.zhihu_client.deepseek_chat(
                    messages=[{"role": "user", "content": r2_prompt}],
                    temperature=0.7,
                    max_tokens=1500,
                )
                if r2_text:
                    r2_data = self._parse_json_response(r2_text)
                    if r2_data:
                        rounds.append(ClashRound(
                            round_number=2,
                            pro_argument=r2_data["pro"],
                            con_argument=r2_data["con"],
                        ))

            # Round 3
            if len(rounds) >= 2:
                r3_prompt = f"""上一轮反驳：
正方：{rounds[1].pro_argument}
反方：{rounds[1].con_argument}

最终轮：请各自修正立场，找到共识点。
风格要求：{STYLE_GUIDE}

请严格按以下 JSON 格式输出：
{{"pro": "正方最终立场（2-3句）", "con": "反方最终立场（2-3句）"}}"""

                r3_text = self.zhihu_client.deepseek_chat(
                    messages=[{"role": "user", "content": r3_prompt}],
                    temperature=0.7,
                    max_tokens=1500,
                )
                if r3_text:
                    r3_data = self._parse_json_response(r3_text)
                    if r3_data:
                        rounds.append(ClashRound(
                            round_number=3,
                            pro_argument=r3_data["pro"],
                            con_argument=r3_data["con"],
                        ))

            return rounds if len(rounds) == 3 else (rounds if rounds else None)

        except Exception as e:
            logger.error(f"LLM fallback rounds failed: {e}")
            return rounds if rounds else None

    # ── 热榜 API 集成 ─────────────────────────────────

    def _fetch_hot_topics(self) -> List[Dict]:
        """从知乎热榜获取争议话题（规则引擎，不用直答）

        缓存 1 小时（热榜变化不快）
        """
        # 内存缓存：1 小时
        if self._hot_topics_cache and (time.time() - self._hot_topics_cache_time < 3600):
            return self._hot_topics_cache

        if not self.zhihu_client:
            return []

        try:
            hot_list = self.zhihu_client.get_hot_list()
            if not hot_list:
                return []

            # 争议性关键词匹配（不用直答，省 API 调用）
            controversy_keywords = [
                "应该", "该不该", "好不好", "对不对", "是不是", "为什么",
                "怎么看", "如何评价", "如何看待", "合理吗", "值得吗",
                "有没有必要", "会不会", "能不能", "要不要", "应不应",
                "取代", "替代", "消失", "淘汰", "禁止", "封杀",
                "升值", "贬值", "泡沫", "危机", "争议", "冲突",
            ]
            exclude_keywords = [
                "去世", "死亡", "遇难", "事故", "灾难", "地震", "火灾",
                "谋杀", "犯罪", "判决", "死刑",
            ]

            topics = []
            for item in hot_list:
                title = item.title
                # 排除纯新闻/悲剧类
                if any(kw in title for kw in exclude_keywords):
                    continue
                # 检查是否有争议性
                if not any(kw in title for kw in controversy_keywords):
                    continue

                # 自动生成正反方标签
                pro, con = self._generate_stance_labels(title)
                if pro and con:
                    topics.append({
                        "id": f"hot_{uuid.uuid4().hex[:6]}",
                        "title": title,
                        "description": item.summary or title,
                        "tags": ["热榜", "争议"],
                        "pro_label": pro,
                        "con_label": con,
                    })

                if len(topics) >= 5:
                    break

            self._hot_topics_cache = topics
            self._hot_topics_cache_time = time.time()
            logger.info(f"Found {len(topics)} hot controversial topics")
            return topics

        except Exception as e:
            logger.error(f"Fetch hot topics failed: {e}")
            return []

    def _generate_stance_labels(self, title: str) -> tuple:
        """根据话题标题自动生成正反方标签"""
        patterns = [
            ("应该", ("应该", "不应该")),
            ("该不该", ("应该", "不应该")),
            ("是不是", ("是", "不是")),
            ("会不会", ("会", "不会")),
            ("能不能", ("能", "不能")),
            ("要不要", ("要", "不要")),
            ("值得吗", ("值得", "不值得")),
            ("合理吗", ("合理", "不合理")),
            ("有没有必要", ("有必要", "没必要")),
            ("取代", ("会被取代", "无法取代")),
            ("禁止", ("应该禁止", "不应禁止")),
            ("贬值", ("正在贬值", "没有贬值")),
            ("泡沫", ("是泡沫", "不是泡沫")),
        ]
        for keyword, (pro, con) in patterns:
            if keyword in title:
                return pro, con
        # 默认
        if "?" in title or "？" in title:
            return "支持", "反对"
        return "", ""

    # ── Internal helpers ──────────────────────────────

    def _find_topic(self, topic_id: str) -> Optional[Dict]:
        """查找话题（先查热榜，再查预置）"""
        # 查热榜话题
        if self._hot_topics_cache:
            for t in self._hot_topics_cache:
                if t["id"] == topic_id:
                    return t
        # 查预置话题
        for t in PRESET_TOPICS:
            if t["id"] == topic_id:
                return t
        return None

    def _get_mock_rounds(self, topic: Dict) -> List[ClashRound]:
        """使用预置 mock 数据"""
        rounds = []
        mock = topic.get("mock_rounds", {})
        for n in ("1", "2", "3"):
            if n in mock:
                rounds.append(ClashRound(
                    round_number=int(n),
                    pro_argument=mock[n]["pro"],
                    con_argument=mock[n]["con"],
                ))
        return rounds

    def _parse_json_response(self, text: str, expect_list: bool = False) -> Optional[any]:
        """解析 LLM 返回的 JSON"""
        json_str = text
        if "```json" in text:
            json_str = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            json_str = text.split("```")[1].split("```")[0]

        result = json.loads(json_str.strip())

        if expect_list:
            if isinstance(result, list):
                return result
            return None

        if isinstance(result, dict) and "pro" in result and "con" in result:
            return result
        return None

    def _verdict_message(self, v: VerdictRequest) -> str:
        if v.mind_changed:
            return "你的想法变了。这不是动摇，是成长。"
        if v.winner == "tie":
            return "平局。双方都有理，这就是争议话题的魅力。"
        winner_label = "正方" if v.winner == "pro" else "反方"
        return f"{winner_label}说服了你。碰撞结束，思考继续。"
