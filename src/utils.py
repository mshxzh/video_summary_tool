import base64


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
"""

