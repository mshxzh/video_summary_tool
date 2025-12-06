from typing import Dict
import re
import urllib.request
import json
import ssl
import certifi

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable


def create_ssl_context():
    """Create SSL context with proper certificate verification."""
    try:
        # Create SSL context with certifi certificates
        context = ssl.create_default_context(cafile=certifi.where())
        return context
    except Exception:
        # Fallback to default context
        return ssl.create_default_context()


def extract_video_id(url: str) -> str:
    """
    Extracts the video ID from a YouTube URL.
    
    Args:
        url (str): The YouTube URL.
        
    Returns:
        str: The video ID.
    """
    patterns = [
        r'(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'  # Just the video ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    raise ValueError("Could not extract video ID from URL")


def get_video_info(url: str) -> Dict[str, str]:
    """
    Returns the title of the video using YouTube's oEmbed API.

    Args:
        url (str): The URL of the YouTube video.

    Returns:
        Dict[str, str]: A dictionary containing the video title.
    """
    try:
        video_id = extract_video_id(url)
        
        # Use YouTube oEmbed API to get video title
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        
        ssl_context = create_ssl_context()
        request = urllib.request.Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(request, context=ssl_context) as response:
            data = json.loads(response.read().decode())
            title = data.get('title', 'Unknown Title')
        
        return title
        
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            raise RuntimeError("Video is unavailable or private. Please check the YouTube URL and try again.")
        elif e.code == 404:
            raise RuntimeError("Video not found. Please check the YouTube URL and try again.")
        else:
            raise RuntimeError(f"Error fetching video information: HTTP {e.code}")
    except ssl.SSLError as e:
        raise RuntimeError(f"SSL certificate error. Please check your internet connection and try again. Details: {str(e)}")
    except Exception as e:
        if "certificate verify failed" in str(e).lower():
            raise RuntimeError("SSL certificate verification failed. This is common on macOS. Please check your internet connection and try again.")
        else:
            raise RuntimeError(f"Error fetching video information: {str(e)}")


def find_captions(url: str) -> Dict[str, str]:
    """
    Finds all available captions for the video and returns a dictionary of language codes and names.

    Args:
        url (str): The URL of the YouTube video.

    Returns:
        Dict[str, str]: A dictionary containing the language codes and names of the available captions.
    """
    try:
        video_id = extract_video_id(url)
        
        # Create API instance and list transcripts (v1.x API)
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        
        captions = {}
        # Get all available transcripts
        for transcript in transcript_list:
            lang_code = transcript.language_code
            lang_name = transcript.language
            # Add indicator if it's auto-generated
            if transcript.is_generated:
                lang_name = f"{lang_name} (auto-generated)"
            captions[lang_code] = lang_name
        
        return captions
        
    except TranscriptsDisabled:
        return {}
    except NoTranscriptFound:
        return {}
    except VideoUnavailable:
        return {}
    except Exception as e:
        if "certificate verify failed" in str(e).lower():
            raise RuntimeError("SSL certificate verification failed while fetching captions. This is common on macOS. Please check your internet connection and try again.")
        else:
            raise RuntimeError(f"Error fetching captions: {str(e)}")


def retrieve_subtitles(url: str, selected_caption_language: str) -> str:
    """
    Retrieves the subtitles for the video in the preferred language.

    Args:
        url (str): The URL of the YouTube video.
        selected_caption_language (str): The language name (e.g., 'English', 'English (auto-generated)').

    Returns:
        str: The subtitles text.
    """
    try:
        video_id = extract_video_id(url)
        
        # Create API instance and list transcripts (v1.x API)
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        
        # Find the matching transcript by language name
        target_transcript = None
        for transcript in transcript_list:
            lang_name = transcript.language
            if transcript.is_generated:
                lang_name = f"{lang_name} (auto-generated)"
            
            if lang_name == selected_caption_language:
                target_transcript = transcript
                break
        
        if target_transcript is None:
            return ""
        
        # Fetch the transcript data
        transcript_data = target_transcript.fetch()
        
        # Combine all text segments into a single string
        captions_text = " ".join([snippet.text for snippet in transcript_data])
        
        return captions_text

    except TranscriptsDisabled:
        print("Transcripts are disabled for this video")
        return ""
    except NoTranscriptFound:
        print("No transcript found for this video")
        return ""
    except VideoUnavailable:
        print("Video is unavailable")
        return ""
    except Exception as e:
        if "certificate verify failed" in str(e).lower():
            print(f"SSL certificate verification failed: {e}")
            raise RuntimeError("SSL certificate verification failed while retrieving subtitles. This is common on macOS. Please check your internet connection and try again.")
        else:
            print(f"Error retrieving subtitles: {e}")
            return ""
