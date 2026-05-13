import React, { useState, useCallback } from 'react';
import { fetchStaticData, searchAndCrash, armMe } from './api';
import './index.css';

// ── Auth helper ──────────────────────
function useZhihuAuth() {
  const [user, setUser] = useState(null);
  const [checked, setChecked] = useState(false);

  // 用 useEffect 避免渲染阶段跳转
  React.useEffect(() => {
    fetch('/api/auth/me').then(r => r.json()).then(data => {
      if (data.logged_in) {
        setUser(data.user);
        setChecked(true);
      } else {
        // 未登录 → 直接跳知乎 OAuth，不显示页面
        fetch('/api/auth/zhihu/url').then(r => r.json()).then(d => {
          window.location.replace(d.authorize_url);
        }).catch(() => setChecked(true)); // 失败了才显示页面
      }
    }).catch(() => setChecked(true));
  }, []);

  const login = () => {
    fetch('/api/auth/zhihu/url').then(r => r.json()).then(data => {
      window.location.href = data.authorize_url;
    });
  };

  const logout = () => {
    fetch('/api/auth/logout', { method: 'POST' }).then(() => {
      window.location.href = '/';
    });
  };

  return { user, checked, login, logout };
}

function useHash() {
  const [hash, setHash] = useState(window.location.hash || '#/');
  const navigate = useCallback((h) => { window.location.hash = h; }, []);
  const [, forceUpdate] = useState(0);
  useState(() => {
    const fn = () => { setHash(window.location.hash || '#/'); forceUpdate(n => n + 1); };
    window.addEventListener('hashchange', fn);
  });
  return [hash, navigate];
}

function FireIcon() { return <span style={{fontSize:'1.2em'}}>🔥</span>; }

// ══════════════════════════════════════
// 不服 -> 武装 模态框
// ══════════════════════════════════════
function ArmModal({ side, argument, topic, stance, onClose, onArmed }) {
  const [grievance, setGrievance] = useState('');
  const [loading, setLoading] = useState(false);
  const [armed, setArmed] = useState(null);

  const handleArm = async () => {
    setLoading(true);
    try {
      const result = await armMe(topic, stance, grievance, argument);
      setArmed(result);
    } catch (e) {
      alert('武装失败: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  if (armed) {
    return <StanceCard armed={armed} grievance={grievance} userComment={grievance} topic={topic} onClose={onClose} />;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>
        <h2 className="modal-title">👊 不服？说出来</h2>
        <div className="modal-target">
          <div className="modal-target-label">{side === 'pro' ? '🔥 正方说' : '❄️ 反方说'}：</div>
          <div className="modal-target-text">"{(argument || '').slice(0, 100)}..."</div>
        </div>
        <div className="modal-field">
          <label>你觉得哪里不对？（可选）</label>
          <textarea
            className="modal-textarea"
            placeholder="一句话就够，AI 帮你找弹药..."
            value={grievance}
            onChange={e => setGrievance(e.target.value)}
            rows={2}
          />
        </div>
        <button className="arm-btn" onClick={handleArm} disabled={loading}>
          {loading ? '🔍 搜索弹药中...' : '⚔️ 武装我'}
        </button>
      </div>
    </div>
  );
}

// ══════════════════════════════════════
// 我的立场卡片（武装结果 + 分享）
// ══════════════════════════════════════
function StanceCard({ armed, grievance, topic, onClose }) {
  const [userComment, setUserComment] = useState(grievance || '');
  const [showShare, setShowShare] = useState(false);

  const shareText = `我在「熔炉」碰撞了 "${topic}"，${userComment ? '我的看法：' + userComment : '发现了新角度'}。\n\n🔥 来看看正反双方怎么说 → #知乎黑客松`;

  const handleShare = async () => {
    setShowShare(true);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(shareText).then(() => {
      alert('已复制分享文案！');
    });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="stance-card-modal" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>
        <div className="stance-card">
          <div className="stance-card-header">
            <h2>⚔️ 你的弹药库</h2>
            <div className="stance-card-topic">{topic}</div>
          </div>
          <div className="stance-card-args">
            {(armed.arguments || []).map((arg, i) => (
              <div key={i} className="stance-arg">
                <div className="stance-arg-num">{i + 1}</div>
                <div className="stance-arg-body">
                  <div className="stance-arg-point">{arg.point}</div>
                  <div className="stance-arg-source">📎 {arg.source}</div>
                </div>
              </div>
            ))}
          </div>
          {armed.sources && armed.sources.length > 0 && (
            <div className="stance-card-sources">
              <div className="stance-sources-label">来源：</div>
              {armed.sources.slice(0, 3).map((s, i) => (
                <a key={i} className="stance-source-link" href={s.url} target="_blank" rel="noopener noreferrer">
                  {s.title ? s.title.slice(0, 30) : '查看原文'} ↗
                </a>
              ))}
            </div>
          )}
          <div className="stance-card-comment">
            <label>加上你的声音：</label>
            <textarea
              className="stance-comment-input"
              placeholder="一句话，让这个立场变成你的..."
              value={userComment}
              onChange={e => setUserComment(e.target.value)}
              rows={2}
            />
          </div>
          <div className="stance-card-slogan">—— {armed.slogan || '在熔炉碰撞后形成的观点'}</div>
          <div className="stance-card-actions">
            <button className="share-btn-main" onClick={handleShare}>📤 分享我的立场</button>
          </div>
          {showShare && (
            <div className="share-panel">
              <div className="share-text-box">
                <pre className="share-text">{shareText}</pre>
              </div>
              <button className="copy-btn" onClick={handleCopy}>📋 复制分享文案</button>
              <div className="share-hint">粘贴到知乎回答、朋友圈、微博即可</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AuthorCard({ source }) {
  const card = source.author_card;
  if (!card) return null;
  return (
    <div className="author-card">
      <div className="author-card-name">{card.name || source.author}</div>
      {card.verified_field && <div className="author-card-field">📋 {card.verified_field}</div>}
      <div className="author-card-stats">
        {card.years_on_zhihu && <span>🕐 {card.years_on_zhihu}</span>}
        {card.answer_count && <span>✏️ {card.answer_count}回答</span>}
        {card.follower_count && <span>👥 {card.follower_count}</span>}
      </div>
    </div>
  );
}

function ArgCard({ side, text, sources, animKey, aiLabel, topic, onDisagree }) {
  const label = side === 'pro' ? '🔥 正方' : '❄️ 反方';
  return (
    <div className={`arg-card arg-${side}`} key={animKey}>
      <div className="arg-agent">{label}</div>
      <div className="arg-body">
        {(text || '').split('\n\n').map((p,i) => <p key={i}>{p}</p>)}
      </div>
      {aiLabel && <div className="ai-disclaimer">ℹ️ {aiLabel}</div>}
      <button className="disagree-btn" onClick={() => onDisagree && onDisagree(side, text)}>
        👊 不服
      </button>
      {sources && sources.length > 0 && (
        <div className="arg-sources">
          <div className="arg-sources-label">真人来源：</div>
          {sources.slice(0, 3).map((s, i) => (
            <div key={i} className="arg-source-item">
              <AuthorCard source={s} />
              <a className="arg-source-link" href={s.url} target="_blank" rel="noopener noreferrer">
                📎 {s.title ? s.title.slice(0, 30) : '查看原文'} ↗
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════
// PAGE: Home
// ══════════════════════════════════════
function HomePage({ navigate, staticData, onLoad }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResult, setSearchResult] = useState(null);
  const [error, setError] = useState(null);
  const { user, checked, login, logout } = useZhihuAuth();

  // 未确认登录状态前不渲染（避免闪现后跳转）
  if (!checked) {
    return <div style={{display:'flex',justifyContent:'center',alignItems:'center',height:'100vh',color:'#B7A56B'}}>
      🔥 熔炉加载中...
    </div>;
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const result = await searchAndCrash(searchQuery.trim());
      setSearchResult({ ...result, id: 'search_' + Date.now() });
    } catch (e) {
      setError(e.message);
    } finally {
      setSearching(false);
    }
  };

  // If search result, show it inline
  if (searchResult) {
    return <StaticTopicPage topic={searchResult} navigate={() => { setSearchResult(null); }} />;
  }

  return (
    <div className="page page-home">
      <header className="hero">
        <div className="hero-glow" />
        <div className="auth-bar">
          {checked && (user ? (
            <div className="auth-user">
              <img src={user.avatar} alt="" className="auth-avatar" />
              <span className="auth-name">{user.fullname}</span>
              <button className="auth-logout" onClick={logout}>退出</button>
            </div>
          ) : (
            <button className="auth-login" onClick={login}>📘 知乎登录</button>
          ))}
        </div>
        <h1 className="hero-title">熔炉 <span className="hero-sub">Crucible</span></h1>
        <p className="hero-desc">围观观点碰撞，发现自己的想法变了</p>
      </header>

      {/* 搜索入口 */}
      <div className="search-box">
        <input
          className="search-input"
          type="text"
          placeholder="搜一个你在想的问题..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
        />
        <button className="search-btn" onClick={handleSearch} disabled={searching}>
          {searching ? '🔥 碰撞中...' : '🔥 开炉'}
        </button>
      </div>
      {error && <p className="search-error">{error}</p>}

      {/* 静态话题列表 */}
      {staticData && staticData.length > 0 && (
        <section className="topic-grid">
          {staticData.map(t => (
            <button key={t.id} className="topic-card" onClick={() => navigate('#/topic/' + t.id)}>
              <div className="topic-card-header">
                <h2>{t.title}</h2>
              </div>
              <p className="topic-subtitle">{t.description || t.title}</p>
              <div className="topic-tags">
                {(t.tags || []).map(tag => <span key={tag} className="tag">#{tag}</span>)}
              </div>
              <div className="topic-vs">
                <span className="vs-pro">{t.pro_label}</span>
                <span className="vs-divider">VS</span>
                <span className="vs-con">{t.con_label}</span>
              </div>
            </button>
          ))}
        </section>
      )}

      {!staticData && (
        <p style={{textAlign:'center',color:'#B7A56B',marginTop:'2rem'}}>
          点击任意话题查看碰撞
        </p>
      )}
    </div>
  );
}

// ══════════════════════════════════════
// PAGE: Static Topic Detail (instant load)
// ══════════════════════════════════════
function StaticTopicPage({ topic, navigate }) {
  const [currentRound, setRound] = useState(1);
  const [initialVote, setInitialVote] = useState(null);
  const [finalVote, setFinalVote] = useState(null);
  const [reflection, setReflection] = useState('');
  const [showRecord, setShowRecord] = useState(false);
  const [animKey, setAnimKey] = useState(0);
  const [armModal, setArmModal] = useState(null); // { side, argument }

  const handleDisagree = (side, argument) => {
    const stance = side === 'pro' ? 'con' : 'pro'; // 不服正方 = 站反方
    setArmModal({ side, argument, stance });
  };

  const rounds = topic.rounds || [];
  const totalRounds = rounds.length;
  const round = rounds[currentRound - 1];

  const changeRound = (n) => { setRound(n); setAnimKey(k => k + 1); };

  if (showRecord) {
    const changed = initialVote !== finalVote;
    const LABELS = {
      pro: topic.pro_label, con: topic.con_label, neutral: '还没想好',
    };
    return (
      <div className="page page-record">
        <button className="back-btn" onClick={() => navigate('#/')}>← 回到熔炉</button>
        <div className="record-card">
          <h1>碰撞记录</h1>
          <h2 className="record-topic">{topic.title}</h2>
          <div className="record-visual">
            <div className="record-side">
              <div className="record-label">碰撞前</div>
              <div className={`record-stance stance-${initialVote}`}>{LABELS[initialVote]}</div>
            </div>
            <div className="record-arrow">
              {changed ? '→' : '='}
              <div className={`record-change ${changed?'changed':'unchanged'}`}>{changed ? '变了' : '没变'}</div>
            </div>
            <div className="record-side">
              <div className="record-label">碰撞后</div>
              <div className={`record-stance stance-${finalVote}`}>{LABELS[finalVote]}</div>
            </div>
          </div>
          {changed && <div className="record-insight"><FireIcon /> 思想发生了位移</div>}
          {reflection && (
            <div className="record-reflection">
              <div className="record-reflection-label">你的感悟：</div>
              <blockquote>"{reflection}"</blockquote>
            </div>
          )}
          {/* 完整碰撞过程 */}
          {rounds.length > 0 && (
            <div className="record-rounds">
              <h3>完整碰撞过程</h3>
              {rounds.map(r => (
                <div key={r.round} className="record-round-item">
                  <div className="record-round-label">第{r.round}轮</div>
                  <div className="record-round-args">
                    <div className="record-arg-pro">🔥 {r.pro_argument}</div>
                    <div className="record-arg-con">❄️ {r.con_argument}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {/* 来源链接 */}
          {topic.sources && topic.sources.length > 0 && (
            <div className="record-rounds">
              <h3>观点来源（知乎真人回答）</h3>
              {topic.sources.map((s,i) => (
                <div key={i} className="record-source-item">
                  <AuthorCard source={s} />
                  <a className="arg-source-link" href={s.url} target="_blank" rel="noopener noreferrer" style={{display:'block',margin:'0.3rem 0'}}>
                    📎 {s.title ? s.title.slice(0,50) : '查看原文'} ↗
                  </a>
                </div>
              ))}
            </div>
          )}

          {/* 立场修正统计 */}
          <div className="stance-stats">
            <h3>📊 立场变化追踪</h3>
            <div className="stance-stats-bar">
              <div className="stance-stats-label">碰撞前立场：{initialVote === 'pro' ? topic.pro_label : initialVote === 'con' ? topic.con_label : '还没想好'}</div>
              <div className="stance-stats-arrow">→</div>
              <div className="stance-stats-label">碰撞后立场：{finalVote === 'pro' ? topic.pro_label : finalVote === 'con' ? topic.con_label : '还没想好'}</div>
            </div>
            <div className={`stance-stats-verdict ${changed ? 'verdict-changed' : 'verdict-stable'}`}>
              {changed ? '🔥 你的想法变了。这不是动摇，是成长。' : '✅ 立场不变，但看到的更全面了。'}
            </div>
          </div>

          {/* AI 透明声明 */}
          <div className="ai-transparency">
            <h3>🤖 AI 透明声明</h3>
            <p>碰撞论点由 DeepSeek 基于知乎真实回答分析生成，非原文。引用来源标注了知乎原作者及链接。本产品遵守《深度合成服务标识办法》。</p>
          </div>
        </div>
        <button className="submit-btn" onClick={() => navigate('#/')} style={{marginTop:'2rem'}}>
          继续围观其他话题
        </button>
      </div>
    );
  }

  return (
    <div className="page page-topic">
      <button className="back-btn" onClick={() => navigate('#/')}>← 回到熔炉</button>
      <div className="topic-header">
        <h1>{topic.title}</h1>
      </div>

      {/* 来源链接（顶部） */}
      {topic.sources && topic.sources.length > 0 && (
        <div className="topic-sources-bar">
          <span className="topic-sources-label">来源：</span>
          {topic.sources.slice(0, 4).map((s, i) => (
            <a key={i} className="arg-source-link" href={s.url} target="_blank" rel="noopener noreferrer">
              {s.title ? s.title.slice(0, 25) : '原文'} ↗
            </a>
          ))}
        </div>
      )}

      {initialVote === null ? (
        <div className="vote-panel vote-initial">
          <h2>你站哪边？</h2>
          <div className="vote-buttons">
            <button className="vote-btn vote-pro" onClick={() => setInitialVote('pro')}>{topic.pro_label}</button>
            <button className="vote-btn vote-neutral" onClick={() => setInitialVote('neutral')}>还没想好 🤔</button>
            <button className="vote-btn vote-con" onClick={() => setInitialVote('con')}>{topic.con_label}</button>
          </div>
        </div>
      ) : (
        <>
          <div className="vote-locked">
            你的初始立场：{initialVote === 'pro' ? topic.pro_label : initialVote === 'con' ? topic.con_label : '还没想好'}
          </div>
          <div className="round-tabs">
            {rounds.map((_, i) => (
              <button key={i} className={`round-tab ${i+1===currentRound?'active':''}`} onClick={() => changeRound(i+1)}>
                第{i+1}轮
              </button>
            ))}
            <span className="round-hint">
              {currentRound === 1 ? '开场立论' : currentRound === 2 ? '针锋相对' : '最终陈词'}
            </span>
          </div>
          {round && (
            <div className="arena">
              <div className="arena-col arena-pro">
                <ArgCard side="pro" text={round.pro_argument} sources={topic.sources} animKey={`p-${animKey}`} aiLabel={round.ai_label} topic={topic.title} onDisagree={handleDisagree} />
              </div>
              <div className="arena-clash">
                <div className="clash-icon">⚡</div>
                <div className="clash-line" />
              </div>
              <div className="arena-col arena-con">
                <ArgCard side="con" text={round.con_argument} sources={topic.sources} animKey={`c-${animKey}`} aiLabel={round.ai_label} topic={topic.title} onDisagree={handleDisagree} />
              </div>
            </div>
          )}
          {armModal && (
            <ArmModal
              side={armModal.side}
              argument={armModal.argument}
              topic={topic.title}
              stance={armModal.stance}
              onClose={() => setArmModal(null)}
              onArmed={() => setArmModal(null)}
            />
          )}
          {currentRound === totalRounds && finalVote === null && (
            <div className="vote-panel vote-final">
              <h2>看完碰撞，你的想法变了吗？</h2>
              <div className="vote-buttons">
                <button className="vote-btn vote-pro" onClick={() => setFinalVote('pro')}>{topic.pro_label}</button>
                <button className="vote-btn vote-neutral" onClick={() => setFinalVote('neutral')}>还没想好 🤔</button>
                <button className="vote-btn vote-con" onClick={() => setFinalVote('con')}>{topic.con_label}</button>
              </div>
            </div>
          )}
          {finalVote !== null && (
            <div className="reflection-panel">
              <div className="reflection-vote-locked">
                你的最终立场：{finalVote === 'pro' ? topic.pro_label : finalVote === 'con' ? topic.con_label : '还没想好'}
              </div>
              <label className="reflection-label">写一句你的感悟（可选）：</label>
              <textarea className="reflection-input" placeholder="看完了碰撞，你心里咯噔了一下吗？"
                value={reflection} onChange={e => setReflection(e.target.value)} rows={3} />
              <button className="submit-btn" onClick={() => setShowRecord(true)}>生成碰撞记录 🔥</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ══════════════════════════════════════
// ROOT
// ══════════════════════════════════════
export default function App() {
  const [hash, navigate] = useHash();
  const [staticData, setStaticData] = useState(null);

  // Load static data once
  useState(() => {
    fetchStaticData().then(setStaticData).catch(() => {});
  });

  const path = hash.replace(/^#\/?/, '/') || '/';

  // Static topic page
  if (path.startsWith('/topic/') && staticData) {
    const topicId = path.replace('/topic/', '');
    const topic = staticData.find(t => t.id === topicId);
    if (topic) {
      return <StaticTopicPage topic={topic} navigate={navigate} />;
    }
  }

  return <HomePage navigate={navigate} staticData={staticData} />;
}
