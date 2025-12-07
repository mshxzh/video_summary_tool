import base64
import streamlit as st


def get_base64(image_path):
    with open(image_path, "rb") as file:
        return base64.b64encode(file.read()).decode()

def convert_youtube_url(url):
    """
    Converts a standard YouTube video URL to an embeddable URL format.

    Standard YouTube URLs look like:
    'https://www.youtube.com/watch?v=<video_id>'
    or
    'https://youtu.be/<video_id>'

    To embed these videos, the URL should be in the format:
    'https://www.youtube.com/embed/<video_id>'

    Parameters:
        url (str): The original URL of the YouTube video.

    Returns:
        str: The embeddable URL for the YouTube video.
    """
    import re

    # Extract video ID using regex
    match = re.search(r"(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})", url)
    if not match:
        raise ValueError("Invalid YouTube URL")

    video_id = match.group(1)

    # Construct the embeddable URL
    embed_url = f"https://www.youtube.com/embed/{video_id}"

    return embed_url

def style_css(background_image):
    return f"""
    <style>
        /* General styles */
        .small-text {{ font-size: 16px; color: #ffffff; margin-bottom: -10px;}}
         
        /* Header styling */
        header[data-testid="stHeader"] {{ background-color: rgba(0, 0, 0, 0.3); color: white; padding: 20px; }}
        /* Main content styling */
        .stApp {{
            background-image: url("data:image/jpg;base64,{background_image}");
            background-size: cover;
        }}
        /* Area styling */
        [data-testid="stExpander"] summary {{
            color: white !important;  /* Expander title */
        }}
        [data-testid="stSidebar"] .stTextInput input::placeholder {{
            color: rgba(255, 255, 255, 0.5) !important;
        }}
        .area-title {{
            font-size: 24px;
            font-weight: bold;
            color: #ffffff;
            margin-bottom: 15px;
            margin-top: 30px;
            display: flex;
            align-items: center;
        }}
    </style>

    <p style="text-align:center; font-size:40px; color:#ffffff; font-weight: bold">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">Know Your YouTube Videos
    </p>
    <div class="small-text"><p style="text-align:center;">Get summaries from YouTube video subtitles, analyze comments and get sentiment analysis</p></div>
    <br>
    <div class="small-text"><p style="text-align:center; font-size:15px; font-weight: bold">⚠️ Disclaimer: for educational purposes only! ⚠️</p></div>
"""


def get_cached_comments(video_id: str, max_comments: int) -> list:
    """
    Get comments with caching. Only fetches additional comments if needed.
    
    Args:
        video_id: YouTube video ID
        max_comments: Maximum number of comments to return
        
    Returns:
        List of comment dictionaries
    """
    cache = st.session_state.comments_cache
    
    # If cache exists for this video and has enough comments, return from cache
    if cache and cache.get("video_id") == video_id:
        cached_comments = cache.get("comments", [])
        cached_count = len(cached_comments)
        
        # If we have enough cached comments, return them (no API call needed)
        if cached_count >= max_comments:
            st.info(f"✅ Using {max_comments} comments from cache ({cached_count} total cached)")
            return cached_comments[:max_comments]
        
        # If no more comments available (next_page_token is exhausted), return what we have
        if cache.get("next_page_token") is None and cached_count > 0:
            st.warning(f"⚠️ Only {cached_count} comments available for this video (requested {max_comments})")
            return cached_comments
        
        # Need to fetch more comments - fetch only the additional ones needed
        additional_needed = max_comments - cached_count
        st.info(f"📥 Fetching {additional_needed} additional comments (already have {cached_count} cached)")
        
        new_comments, next_token = _fetch_comments_with_token(
            video_id, 
            additional_needed, 
            cache.get("next_page_token")
        )
        
        # Update cache
        all_comments = cached_comments + new_comments
        st.session_state.comments_cache = {
            "video_id": video_id,
            "comments": all_comments,
            "next_page_token": next_token
        }
        
        # Check if we got fewer than requested (video has limited comments)
        if len(all_comments) < max_comments and next_token is None:
            st.warning(f"⚠️ Only {len(all_comments)} comments available for this video")
        
        return all_comments[:max_comments]
    
    # No cache or different video - fetch fresh
    st.info(f"📥 Fetching {max_comments} comments...")
    comments, next_token = _fetch_comments_with_token(video_id, max_comments, None)
    
    # Store in cache
    st.session_state.comments_cache = {
        "video_id": video_id,
        "comments": comments,
        "next_page_token": next_token
    }
    
    # Check if video has fewer comments than requested
    if len(comments) < max_comments and next_token is None:
        st.warning(f"⚠️ Only {len(comments)} comments available for this video")
    
    return comments


def display_cache_status():
    """Display current cache status in the UI."""
    cache = st.session_state.comments_cache
    if cache:
        cached_count = len(cache.get("comments", []))
        has_more = cache.get("next_page_token") is not None
        more_text = " (more available)" if has_more else " (all fetched)"
        st.caption(f"💾 Cache: {cached_count} comments{more_text}")
    else:
        st.caption("💾 Cache: empty")


def _fetch_comments_with_token(video_id: str, max_comments: int, page_token: str = None) -> tuple:
    """
    Fetch comments from YouTube API with pagination support.
    
    Returns:
        Tuple of (comments_list, next_page_token)
    """
    import os
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError("YouTube API not available. Install google-api-python-client.")
    
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY not set in environment variables.")
    
    youtube = build("youtube", "v3", developerKey=api_key)
    comments = []
    next_page_token = page_token
    
    while len(comments) < max_comments:
        resp = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            order="relevance",
            pageToken=next_page_token
        ).execute()
        
        for item in resp.get("items", []):
            s = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "id": item.get("id"),
                "text": s.get("textDisplay", "") if isinstance(s, dict) else "",
                "author": s.get("authorDisplayName") if isinstance(s, dict) else None,
                "published_at": s.get("publishedAt") if isinstance(s, dict) else None,
                "like_count": s.get("likeCount", 0) if isinstance(s, dict) else 0
            })
            if len(comments) >= max_comments:
                break
        
        next_page_token = resp.get("nextPageToken")
        if not next_page_token:
            break
    
    return comments, next_page_token

