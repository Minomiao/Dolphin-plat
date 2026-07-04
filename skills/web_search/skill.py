import re
import requests
from typing import Dict, Any, List
from colorama import Fore, Style
from modules.bootstrap import constants


skill_info = {
    "name": "web_search",
    "description": "网络搜索技能，可以搜索网络信息",
    "functions": {
        "search": {
            "description": "搜索网络信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "num_results": {"type": "integer", "description": "返回结果数量，默认为5"}
                },
                "required": ["query"]
            }
        },
        "fetch": {
            "description": "解析指定网址的网页内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要解析的网页URL"}
                },
                "required": ["url"]
            }
        }
    }
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_FILTER_THRESHOLD = 0.5

# ---- 关键字匹配回退 ----
_KEYWORD_MIN_LEN = 2
_STOP_WORDS = {
    "的", "是", "了", "在", "和", "与", "或", "不", "有", "我", "他", "她", "它",
    "这", "那", "都", "也", "就", "还", "要", "会", "能", "对", "把", "被", "让",
    "从", "到", "很", "更", "最", "已", "着", "呢", "吗", "吧", "啊", "哦", "嗯",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must", "in", "on", "at",
    "to", "for", "of", "with", "by", "from", "as", "or", "and", "not",
    "but", "if", "so", "no", "up", "out", "all", "any", "both", "each",
    "few", "more", "most", "other", "some", "such", "only", "own", "same",
    "than", "too", "very", "just", "about", "into", "over", "also",
}


def _extract_keywords(query: str) -> List[str]:
    """从查询中提取有意义的关键字（用于模型不可用时的回退过滤）。"""
    cleaned = re.sub(r'[^\w\s]', ' ', query).strip()
    tokens = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', cleaned)
    return [t.lower() for t in tokens if t.lower() not in _STOP_WORDS and len(t) >= _KEYWORD_MIN_LEN]


def _build_user_output(query: str, results: list) -> str:
    gray = Fore.LIGHTBLACK_EX
    reset = Style.RESET_ALL
    return f'"{query}"{gray} - {len(results)} results{reset}'


# ---- 相关性过滤（由 skill 自己决策）----

def _filter_relevant(context, query: str, results: List[Dict]) -> List[Dict]:
    """
    对搜索结果做相关性过滤。
    优先级: 向量相似度 > 关键字匹配 > 原始结果
    """
    if not results:
        return results

    # 尝试向量化
    embs = None
    try:
        embs = context.encode_texts([query] + [f"{r.get('title', '')} {r.get('content', '')}" for r in results])
    except Exception:
        embs = None

    if embs is not None and len(embs) == len(results) + 1:
        # 向量相似度过滤
        import numpy as np
        query_emb = embs[0:1]       # (1, 512)
        doc_embs = embs[1:]          # (n, 512)
        similarities = np.dot(doc_embs, query_emb.T).flatten()

        filtered = [r for r, sim in zip(results, similarities) if float(sim) >= _FILTER_THRESHOLD]
        return filtered if filtered else results

    # 回退：关键字匹配
    keywords = _extract_keywords(query)
    if not keywords:
        return results

    filtered = []
    for r in results:
        text = (r.get("title", "") + " " + r.get("content", "")).lower()
        if any(kw in text for kw in keywords):
            filtered.append(r)

    return filtered if filtered else results


# ---- 搜索入口 ----

def search(context, query: str, num_results: int = 5) -> Dict[str, Any]:
    try:
        url = "https://www.bing.com/search"
        params = {"q": query, "count": num_results}
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text

        results = []
        # 匹配 Bing 搜索结果: <li class="b_algo"> ... </li>
        blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)

        for block in blocks:
            if len(results) >= num_results:
                break

            # 提取 h2 中的链接和标题
            h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
            if not h2_match:
                continue

            h2_content = h2_match.group(1)
            link_match = re.search(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', h2_content, re.DOTALL)
            if not link_match:
                continue

            url_val = link_match.group(1)
            title = re.sub(r'<[^>]+>', '', link_match.group(2)).strip()
            if not title:
                continue

            # 提取摘要
            caption_match = re.search(r'<div class="b_caption"[^>]*>(.*?)</div>', block, re.DOTALL)
            snippet = ""
            if caption_match:
                p_match = re.search(r'<p[^>]*>(.*?)</p>', caption_match.group(1), re.DOTALL)
                if p_match:
                    snippet = re.sub(r'<[^>]+>', '', p_match.group(1)).strip()

            results.append({
                "title": title,
                "content": snippet,
                "url": url_val
            })

        # 相关性过滤（skill 自己决策）
        if context and results:
            results = _filter_relevant(context, query, results)

        return {
            "query": query,
            "results": results,
            "user_output": {"label": "Search", "content": _build_user_output(query, results)}
        }

    except Exception as e:
        return {
            "error": str(e),
            "query": query,
            "results": [],
            "user_output": {"label": "Search", "content": f'{Fore.LIGHTBLACK_EX}"{query}" - Error{Style.RESET_ALL}'}
        }


# ---- 网页解析 ----

def fetch(context, url: str) -> Dict[str, Any]:
    """解析指定网址的网页内容。"""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text

        # 提取标题
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""

        # 移除脚本和样式
        cleaned = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # 移除所有标签
        text = re.sub(r'<[^>]+>', ' ', cleaned)
        # 清理空白
        text = re.sub(r'\s+', ' ', text).strip()

        # 截断过长的内容
        if len(text) > constants.MAX_WEB_CONTENT_LENGTH:
            text = text[:constants.MAX_WEB_CONTENT_LENGTH] + "..."

        return {
            "url": url,
            "title": title,
            "content": text,
            "user_output": {"label": "Fetch", "content": f'{Fore.LIGHTBLACK_EX}"{title or url}" - OK{Style.RESET_ALL}'}
        }

    except Exception as e:
        return {
            "error": str(e),
            "url": url,
            "content": "",
            "user_output": {"label": "Fetch", "content": f'{Fore.LIGHTBLACK_EX}"{url}" - Error{Style.RESET_ALL}'}
        }
