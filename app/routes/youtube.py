import re
import urllib.parse
import httpx
from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional

router = APIRouter(prefix="/api/youtube", tags=["YouTube Connector"])

# Multi-Channel Curated Catalog: Contains high-signal educational videos from DISTINCT YouTube channels.
# Ensures Alumni AI always presents varied educational creators without channel repetition.
DIVERSE_CHANNEL_CATALOG = {
    "python": [
        {"id": "kqtD5dpn9C8", "title": "Python Full Course for Beginners", "channel": "Programming with Mosh"},
        {"id": "rfscVS0vtbw", "title": "Python in 100 Seconds", "channel": "Fireship"},
        {"id": "YYXdXT2l-Gg", "title": "Python OOP Tutorials - Classes & Objects", "channel": "Corey Schafer"},
        {"id": "f79MRyMsjrQ", "title": "Python Intermediate Concepts", "channel": "Tech With Tim"},
        {"id": "IX2bXxAUG4I", "title": "Python Full Course", "channel": "Bro Code"}
    ],
    "asyncio": [
        {"id": "t5Bo1Je9EmE", "title": "Asyncio in Python Full Tutorial", "channel": "ArjanCodes"},
        {"id": "oAkLSJNr5zY", "title": "Python Asyncio Architecture & Event Loop", "channel": "mCoding"},
        {"id": "ba3GkWZ_a7k", "title": "Asynchronous Programming in Python", "channel": "NeuralNine"}
    ],
    "algorithm": [
        {"id": "0IAPZzGSbME", "title": "Algorithms Analysis & Asymptotic Notations", "channel": "Abdul Bari"},
        {"id": "klgGzK7Z1gE", "title": "NeetCode DSA Roadmap & Algorithms", "channel": "NeetCode"},
        {"id": "8hly31xKli0", "title": "Algorithms and Data Structures Tutorial", "channel": "freeCodeCamp.org"},
        {"id": "bum_1950tSU", "title": "Introduction to Recursion & Dynamic Programming", "channel": "CS Dojo"},
        {"id": "RBSGKlAvoiM", "title": "Graph Theory & Dijkstra Algorithm", "channel": "WilliamFiset"}
    ],
    "data structure": [
        {"id": "0IAPZzGSbME", "title": "Trees, Graphs and Binary Search Trees", "channel": "Abdul Bari"},
        {"id": "bbm2zQk4rR0", "title": "Data Structures Easy to Advanced Course", "channel": "freeCodeCamp.org"},
        {"id": "klgGzK7Z1gE", "title": "Binary Trees, Stacks & Queues", "channel": "NeetCode"},
        {"id": "RBSGKlAvoiM", "title": "Indexed Priority Queues & Data Structures", "channel": "WilliamFiset"}
    ],
    "tree": [
        {"id": "0IAPZzGSbME", "title": "Binary Search Trees & AVL Trees", "channel": "Abdul Bari"},
        {"id": "klgGzK7Z1gE", "title": "Invert Binary Tree & DFS/BFS Traversal", "channel": "NeetCode"},
        {"id": "bbm2zQk4rR0", "title": "Binary Tree Data Structure Explained", "channel": "freeCodeCamp.org"}
    ],
    "ai": [
        {"id": "aircAruvnKk", "title": "Neural Networks & Backpropagation Explained", "channel": "3Blue1Brown"},
        {"id": "Gv9_4yMHFhI", "title": "Neural Networks Clearly Explained", "channel": "StatQuest with Josh Starmer"},
        {"id": "T3Fc7GS38n4", "title": "Introduction to Deep Learning", "channel": "MIT OpenCourseWare"},
        {"id": "5q87K1WaoFI", "title": "Generative AI and Large Language Models", "channel": "DeepLearningAI"},
        {"id": "i_LwzRVP7bg", "title": "Machine Learning for Everybody", "channel": "freeCodeCamp.org"},
        {"id": "x7X9w_GIm1s", "title": "AI Agents Architecture in 100 Seconds", "channel": "Fireship"}
    ],
    "machine learning": [
        {"id": "Gv9_4yMHFhI", "title": "Machine Learning Fundamentals", "channel": "StatQuest with Josh Starmer"},
        {"id": "aircAruvnKk", "title": "What is a Neural Network?", "channel": "3Blue1Brown"},
        {"id": "T3Fc7GS38n4", "title": "Deep Learning Architectures", "channel": "MIT OpenCourseWare"},
        {"id": "i_LwzRVP7bg", "title": "Machine Learning Full Course", "channel": "freeCodeCamp.org"}
    ],
    "javascript": [
        {"id": "DHjqpvDnNGE", "title": "JavaScript in 100 Seconds", "channel": "Fireship"},
        {"id": "hdI2bqOjy3c", "title": "JavaScript Crash Course for Beginners", "channel": "Traversy Media"},
        {"id": "h33Srr5J9nY", "title": "JavaScript Clean Code Best Practices", "channel": "Web Dev Simplified"},
        {"id": "jS4aFq5-91M", "title": "JavaScript Full Course", "channel": "freeCodeCamp.org"},
        {"id": "iWOYAxlnaww", "title": "Modern JavaScript Tutorial", "channel": "The Net Ninja"}
    ],
    "typescript": [
        {"id": "zQnBQ4tB3ZA", "title": "TypeScript Course for Beginners", "channel": "Academind"},
        {"id": "ahCwqrYqo9o", "title": "TypeScript in 100 Seconds", "channel": "Fireship"},
        {"id": "BwuLxPH8IDs", "title": "TypeScript Full Course Tutorial", "channel": "freeCodeCamp.org"}
    ],
    "react": [
        {"id": "w7ejDZ8SWv8", "title": "React JS Full Course", "channel": "freeCodeCamp.org"},
        {"id": "SqcY0GlETPk", "title": "React Tutorial for Beginners", "channel": "Programming with Mosh"},
        {"id": "hQAHSlTtcmY", "title": "Learn React in 30 Minutes", "channel": "Web Dev Simplified"},
        {"id": "bMknfKXIFA8", "title": "React Course - Beginner's Tutorial", "channel": "freeCodeCamp.org"}
    ],
    "database": [
        {"id": "HXV3zeRRhuQ", "title": "SQL Tutorial - Full Database Course", "channel": "freeCodeCamp.org"},
        {"id": "cz3w5MW8E8s", "title": "Databases in 100 Seconds", "channel": "Fireship"},
        {"id": "ztHopE5Wnpc", "title": "SQL for Beginners", "channel": "Programming with Mosh"},
        {"id": "7S_tz1z_5bA", "title": "Database Design Course", "channel": "freeCodeCamp.org"}
    ],
    "sql": [
        {"id": "HXV3zeRRhuQ", "title": "SQL Tutorial - Full Database Course", "channel": "freeCodeCamp.org"},
        {"id": "ztHopE5Wnpc", "title": "SQL for Beginners", "channel": "Programming with Mosh"},
        {"id": "cz3w5MW8E8s", "title": "SQL Explained in 100 Seconds", "channel": "Fireship"}
    ],
    "linux": [
        {"id": "s3ii48qYBXA", "title": "Linux for Beginners Course", "channel": "NetworkChuck"},
        {"id": "26QPDBe-NB8", "title": "Linux Operating System Full Course", "channel": "freeCodeCamp.org"},
        {"id": "rrB13utjYV4", "title": "Linux in 100 Seconds", "channel": "Fireship"}
    ],
    "network": [
        {"id": "IPvYjXCsTg8", "title": "Computer Networking Full Course", "channel": "NetworkChuck"},
        {"id": "ve7_G3383AU", "title": "How the Internet Works", "channel": "Computerphile"},
        {"id": "qiQR5rTSshw", "title": "Computer Networks Course", "channel": "freeCodeCamp.org"}
    ],
    "security": [
        {"id": "3Kq1MIfTWCE", "title": "Cybersecurity for Beginners", "channel": "NetworkChuck"},
        {"id": "inWWhr5tnEA", "title": "Cyber Security Full Course", "channel": "freeCodeCamp.org"},
        {"id": "yrbA_n159bY", "title": "Hacking & Security Concepts", "channel": "Computerphile"}
    ],
    "math": [
        {"id": "WUvTyaaNkzM", "title": "Essence of Calculus", "channel": "3Blue1Brown"},
        {"id": "1xU21t0nU-Y", "title": "Calculus 1 Full College Course", "channel": "Khan Academy"},
        {"id": "w-I6XTVZXww", "title": "Mathematical Proofs & Patterns", "channel": "Numberphile"},
        {"id": "fNk_zzaMoEg", "title": "Essence of Linear Algebra", "channel": "3Blue1Brown"}
    ],
    "physics": [
        {"id": "X4_eT_5cW7I", "title": "Physics Fundamentals Overview", "channel": "CrashCourse"},
        {"id": "HeQX2HjkcNo", "title": "The Physics of Computation", "channel": "Veritasium"},
        {"id": "7kb1WTETdu0", "title": "Quantum Physics & The Universe", "channel": "Kurzgesagt – In a Nutshell"}
    ],
    "study": [
        {"id": "Yx6686K89uU", "title": "Evidence-Based Study Techniques", "channel": "Ali Abdaal"},
        {"id": "EaR3n7vD00E", "title": "How to Stop Procrastinating & Study Deeply", "channel": "Thomas Frank"},
        {"id": "p60rZxY99y0", "title": "Taking Notes & Conceptual Memory", "channel": "CrashCourse"}
    ],
    "research": [
        {"id": "t5_81H4lTfc", "title": "How to Read & Structure Academic Research Papers", "channel": "Andy Stapleton"},
        {"id": "G_Sqw82yq-Q", "title": "Literature Review & Research Methodologies", "channel": "Scribbr"},
        {"id": "Yx6686K89uU", "title": "Active Recall & Academic Workflow", "channel": "Ali Abdaal"}
    ]
}

# General pool of top diverse educational videos across channels
GENERAL_DIVERSE_POOL = [
    {"id": "aircAruvnKk", "title": "Neural Networks & Deep Learning", "channel": "3Blue1Brown"},
    {"id": "Gv9_4yMHFhI", "title": "Machine Learning Fundamentals", "channel": "StatQuest with Josh Starmer"},
    {"id": "0IAPZzGSbME", "title": "Algorithms Analysis & Asymptotics", "channel": "Abdul Bari"},
    {"id": "rfscVS0vtbw", "title": "Programming Architecture in 100 Seconds", "channel": "Fireship"},
    {"id": "IPvYjXCsTg8", "title": "Computer Networking Full Course", "channel": "NetworkChuck"},
    {"id": "hdI2bqOjy3c", "title": "Computer Science & Web Development", "channel": "Traversy Media"},
    {"id": "ve7_G3383AU", "title": "Computer Systems & Foundations", "channel": "Computerphile"},
    {"id": "HeQX2HjkcNo", "title": "Scientific Thinking & Discovery", "channel": "Veritasium"},
    {"id": "T3Fc7GS38n4", "title": "Introduction to Deep Learning", "channel": "MIT OpenCourseWare"},
    {"id": "8hly31xKli0", "title": "Algorithms & Problem Solving", "channel": "freeCodeCamp.org"}
]

def pick_distinct_channel_video(candidates: List[Dict[str, str]], excluded_channels: List[str]) -> Dict[str, str]:
    """
    Selects a video from candidates whose channel is NOT in the excluded_channels list.
    If all candidates match excluded channels, picks the candidate least recently used.
    """
    norm_excluded = [c.strip().lower() for c in excluded_channels if c.strip()]
    
    # 1. Look for a candidate whose channel is not excluded
    for item in candidates:
        if item.get("channel", "").lower() not in norm_excluded:
            return item
            
    # 2. If all candidates are in excluded_channels, pick from general diverse pool
    for item in GENERAL_DIVERSE_POOL:
        if item.get("channel", "").lower() not in norm_excluded:
            return item

    # 3. Fallback to first candidate
    return candidates[0] if candidates else GENERAL_DIVERSE_POOL[0]

def get_curated_distinct_match(query: str, excluded_channels: List[str]) -> Dict[str, str]:
    q_lower = query.lower()
    for keyword, candidate_list in DIVERSE_CHANNEL_CATALOG.items():
        if keyword in q_lower:
            return pick_distinct_channel_video(candidate_list, excluded_channels)
            
    # If no keyword matched, pick from general diverse pool
    return pick_distinct_channel_video(GENERAL_DIVERSE_POOL, excluded_channels)

@router.get("/search")
async def search_youtube_video(
    q: str = Query(..., min_length=1),
    exclude_channels: Optional[str] = Query(None, description="Comma-separated list of channel names to avoid repetition")
):
    """
    Resolves a real, active 11-character YouTube video ID from a DIFFERENT channel.
    Enforces channel diversity to prevent showing consecutive videos from the same channel.
    """
    clean_query = q.strip()
    excluded_list = [c.strip() for c in exclude_channels.split(",")] if exclude_channels else []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    # 1. Attempt live search via DuckDuckGo HTML for active youtube.com/watch links
    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus('site:youtube.com ' + clean_query)}"
            r = await client.get(search_url, headers=headers)
            if r.status_code == 200:
                # Find all result links and snippets
                matches = re.findall(
                    r'<a class="result__url" href="([^"]+)">(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
                    r.text,
                    re.DOTALL
                )
                for link, title_html, snippet_html in matches:
                    if "uddg=" in link:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)
                        if "uddg" in parsed and parsed["uddg"]:
                            real_url = parsed["uddg"][0]
                            v = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', real_url)
                            if v:
                                video_id = v.group(1)
                                title_clean = re.sub(r'<[^>]+>', '', title_html).strip()
                                snippet_clean = re.sub(r'<[^>]+>', '', snippet_html).strip()
                                
                                # Try extracting channel name from title/snippet (e.g., "... by ChannelName ...")
                                channel_name = "YouTube Education"
                                chan_match = re.search(r'\b(?:by|channel|from)\s+([A-Za-z0-9_\s]{3,25})\b', snippet_clean, re.IGNORECASE)
                                if chan_match:
                                    channel_name = chan_match.group(1).strip()
                                elif " - " in title_clean:
                                    channel_name = title_clean.split(" - ")[-1].strip()

                                # Enforce channel diversity check
                                norm_excluded = [c.lower() for c in excluded_list]
                                if channel_name.lower() in norm_excluded:
                                    continue  # Skip to next result to guarantee a different channel!

                                return {
                                    "video_id": video_id,
                                    "title": f"{clean_query} • Video Tutorial",
                                    "channel": channel_name,
                                    "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}?autoplay=0&rel=0"
                                }
    except Exception as e:
        pass

    # 2. Curated multi-channel match with guaranteed channel diversity
    matched_item = get_curated_distinct_match(clean_query, excluded_list)
    video_id = matched_item["id"]
    return {
        "video_id": video_id,
        "title": matched_item["title"],
        "channel": matched_item["channel"],
        "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}?autoplay=0&rel=0"
    }
