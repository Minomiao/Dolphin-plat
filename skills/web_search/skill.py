import re
import requests
from typing import Dict, Any
from colorama import Fore, Style


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
        }
    }
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_SNIPPET_WIDTH = 50

def _strip_html(s: str) -> str:
    s = re.sub(r'&[a-z]+;', '', s)
    s = re.sub(r'&#\d+;', '', s)
    return s

def _truncate(s: str, width: int) -> str:
    s = _strip_html(s)
    if len(s) > width:
        return s[:width - 1] + "…"
    return s

def _build_user_output(query: str, results: list) -> str:
    gray = Fore.LIGHTBLACK_EX
    reset = Style.RESET_ALL
    lines = [f'"{query}"{gray} - {len(results)} results{reset}']

    for r in results:
        snippet = _truncate(r["content"] or r["title"], _SNIPPET_WIDTH)
        lines.append(f'{gray}  {snippet}{reset}')

    return "\n".join(lines)


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

        # 使用嵌入模型过滤不相关结果
        if context and results:
            results = context.filter_relevant(query, results)

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
