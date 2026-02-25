import requests
from typing import Dict, Any


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


def search(query: str, num_results: int = 5) -> Dict[str, Any]:
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        
        if "AbstractText" in data and data["AbstractText"]:
            results.append({
                "title": data.get("Heading", ""),
                "content": data["AbstractText"],
                "url": data.get("AbstractURL", "")
            })
        
        if "RelatedTopics" in data:
            for topic in data["RelatedTopics"][:num_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                        "content": topic["Text"],
                        "url": topic.get("FirstURL", "")
                    })
        
        return {
            "query": query,
            "results": results[:num_results]
        }
    
    except Exception as e:
        return {
            "error": str(e),
            "query": query,
            "results": []
        }
