// API client for Crucible backend
const API_BASE = 'http://localhost:8003';

async function api(path, opts = {}) {
  const url = API_BASE + path;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// 获取预生成的静态数据（秒开）
export async function fetchStaticData() {
  return api('/api/static');
}

// 搜索入口（实时生成碰撞）
export async function searchAndCrash(query) {
  return api('/api/search-topic', {
    method: 'POST',
    body: JSON.stringify({ query }),
  });
}

// 不服 -> 武装：用户输入不服点，AI 帮找论据
export async function armMe(topic, stance, grievance, targetArgument) {
  return api('/api/arm', {
    method: 'POST',
    body: JSON.stringify({
      topic,
      user_stance: stance,
      grievance,
      target_argument: targetArgument,
    }),
  });
}

// 旧接口保留（兼容）
export async function fetchTopics() {
  const data = await api('/api/topics');
  return (data.topics || data).map(t => ({
    id: t.id,
    title: t.title,
    subtitle: t.description,
    heat: Math.floor(Math.random() * 3000) + 500,
    tags: t.tags || [],
    pro_label: t.pro_label,
    con_label: t.con_label,
  }));
}
