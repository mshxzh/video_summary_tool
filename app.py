import re
import time

import streamlit as st
import plotly.express as px
import pandas as pd

from src.media_processing import get_video_info, find_captions, retrieve_subtitles
from src.comments_classification import fetch_top_comments_from_youtube, predict_sentiment, clean_text, clean_text_for_display
from src.llm_actions import *
from src.utils import *


# Set the page configuration (should be at the top)
st.set_page_config(page_title="Know Your YouTube Videos", layout='centered', page_icon=":material/subtitles:")

# Background image https://unsplash.com/photos/blue-and-yellow-abstract-painting-1xZ0SqLPE4E
background_image = get_base64('src/background.jpg')  # Replace with your light theme image

st.markdown(style_css(background_image), unsafe_allow_html=True)

st.divider() 

# Initialize session state variables
if "summary" not in st.session_state:
    st.session_state.summary = None
if "video_title" not in st.session_state:
    st.session_state.video_title = None
if "previous_url" not in st.session_state:
    st.session_state.previous_url = None
if "disabled_button" not in st.session_state:
    st.session_state.disabled_button = False  # Default to not disabled
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = None
if "use_original_language" not in st.session_state:
    st.session_state.use_original_language = True  # Initialize language preference
if "language_settings_disabled" not in st.session_state:
    st.session_state.language_settings_disabled = False  # Initialize language settings disabled state
if "comments_data" not in st.session_state:
    st.session_state.comments_data = None

if "youtube_key" not in st.session_state:
    st.session_state.youtube_key = 1

if "condition_yt" not in st.session_state:
    st.session_state.condition_yt = False

def clear_outputs():
    st.session_state.summary = None
    st.session_state.comments_data = None
    

def main():
    # Callback functions to update state and rerun UI
    def on_youtube_input():
        # Check if valid YouTube URL is provided
        youtube_pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
        condition_yt = st.session_state[f"yt_{st.session_state.youtube_key}"] != '' and re.match(youtube_pattern, st.session_state[f"yt_{st.session_state.youtube_key}"]) is not None  
    
        st.session_state.condition_yt = condition_yt
    
    st.session_state.api_key_validated = True
    st.session_state.gemini_api_key = 'AIzaSyCExi7D0Dzk4CPzlveF0js9il6Tq6C9DDY'

    # YouTube URL input
    st.text_input(
        "YouTube Link:",
        placeholder="Enter a YouTube video link",
        key=f"yt_{st.session_state.youtube_key}",
        on_change=on_youtube_input
    )

    # Display video if valid URL is provided
    if st.session_state.condition_yt:
        # VIDEO section
        st.markdown('<div class="area-title">Your Video</div>', unsafe_allow_html=True)
        emb_youtube_url = convert_youtube_url(st.session_state[f"yt_{st.session_state.youtube_key}"])
        st.markdown(f'<iframe width="100%" height="450" src="{emb_youtube_url}" frameBorder="0" allow="clipboard-write; autoplay" webkitAllowFullScreen mozallowfullscreen allowFullScreen></iframe>', unsafe_allow_html=True)
        
        title = get_video_info(st.session_state[f"yt_{st.session_state.youtube_key}"])
        st.session_state.video_title = title
        
        st.markdown(f'''
            <p style="font-size: 14px; font-weight: bold; color: #1DB954; margin-bottom: 5px;">Video Details</p>
            <div class="small-text"><p style="font-size: 16px; line-height: 1.3; margin-top: 0; margin-bottom: 25px; color: #ffffff;">{title}</p></div>
            <p style="margin-bottom: 30px;"></p>
        ''', unsafe_allow_html=True)

    # Check if previous URL changed to clear outputs
    if st.session_state.summary is not None or st.session_state.comments_data is not None:
        if (st.session_state.condition_yt and st.session_state.previous_url != st.session_state[f"yt_{st.session_state.youtube_key}"]):
            clear_outputs()
            st.session_state.disabled_button = False
            st.session_state.language_settings_disabled = False

    if st.session_state.condition_yt:
        # Create tabs for Summary and Sentiment Analysis
        tab_summary, tab_comments = st.tabs(["📝 Summary", "💬 Sentiment Analysis"])
        
        # Callback function to disable the button and language settings
        def disable_summary():
            st.session_state.disabled_button = True
            st.session_state.language_settings_disabled = True
        
        # ---------- SUMMARY TAB ----------
        with tab_summary:
            # Section for captions
            with st.expander("Subtitle Settings", expanded=True):
                captions = find_captions(st.session_state[f"yt_{st.session_state.youtube_key}"])
                lang_list = list(captions.values())
                
                if not lang_list:
                    st.error("No subtitles available for this video. Please try a different video.")
                    captions_lang = None
                else:
                    st.success(f"Found {len(lang_list)} subtitle language(s)")
                    captions_lang = st.selectbox(
                        "Available subtitle languages:",
                        lang_list,
                        index=0
                    )

            # Language settings
            with st.expander("Summary language settings"):
                col1, col2 = st.columns([1,1])
                with col1:
                    st.session_state.use_original_language = st.toggle(
                        "Use original language", 
                        value=st.session_state.use_original_language,
                        disabled=st.session_state.language_settings_disabled
                    )
                with col2:
                    lang_option = st.selectbox(
                        "What language do you prefer?",
                        ("English", "Dutch", "Russian"),
                        disabled=st.session_state.use_original_language or st.session_state.language_settings_disabled,
                    )
            if st.session_state.use_original_language:
                lang_option = ""
            
            st.markdown('<p style="margin-bottom: 30px;"></p>', unsafe_allow_html=True)

            # Check if API key is entered and subtitles are available
            if not st.session_state.api_key_validated:
                st.error("Please enter and validate your Gemini API key in the sidebar")
            elif not lang_list:
                st.error("Cannot process video without subtitles. Please choose a video with available subtitles.")
            else:
                # Button to analyze subtitle content
                generate_content_button = st.button("Get Subtitle Summary", 
                        type='primary', 
                        use_container_width=True, 
                        on_click=disable_summary,
                        disabled=st.session_state.disabled_button,
                        key="summary_btn")

                if generate_content_button:
                    start_time = time.time()
                    st.session_state.disabled_button = True
                    with st.spinner("Processing subtitles..."):

                        try:
                            # Get subtitles
                            if captions_lang is None:
                                st.error("No subtitle language selected.")
                                st.session_state.disabled_button = False
                                return
                                
                            subtitles_text = retrieve_subtitles(st.session_state[f"yt_{st.session_state.youtube_key}"], captions_lang)
                            
                            if not subtitles_text.strip():
                                st.error("Could not retrieve subtitles. Please try a different video.")
                                st.session_state.disabled_button = False
                                return
                            
                            st.info(f"Using subtitles in {captions_lang}", icon=":material/closed_caption:")
                            
                            # Process subtitles
                            summary = summarize_text(subtitles_text, chosen_language=lang_option, gemini_key=st.session_state.gemini_api_key)
                            
                            st.session_state.summary = summary
                            st.session_state.previous_url = st.session_state[f"yt_{st.session_state.youtube_key}"]

                            end_time = time.time()
                            elapsed_time = end_time - start_time
                            st.info(f"Time taken: {elapsed_time:.2f} seconds", icon=":material/timer:")
                            
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")
                            st.session_state.disabled_button = False

            if st.session_state.summary:
                with st.expander("Summary", expanded=True):
                    col1, col2 = st.columns([2,1])
                    with col1:
                        if st.button("Re-generate Summary", type='secondary', key="regen_btn"):
                            if not st.session_state.gemini_api_key:
                                st.error("Please enter your Gemini API key in the sidebar")
                                return
                            # Re-get subtitles and regenerate summary
                            captions = find_captions(st.session_state[f"yt_{st.session_state.youtube_key}"])
                            lang_list = list(captions.values())
                            if lang_list:
                                subtitles_text = retrieve_subtitles(st.session_state[f"yt_{st.session_state.youtube_key}"], lang_list[0])
                                summary = summarize_text(subtitles_text, chosen_language=lang_option, gemini_key=st.session_state.gemini_api_key)
                                st.session_state.summary = summary

                    st.markdown(f'''
                        <div style="margin-bottom: 15px;">
                            <p style="font-size: 16px; line-height: 1.5; color: #ffffff;">{st.session_state.summary}</p>
                        </div>
                    ''', unsafe_allow_html=True)
        
        # ---------- SENTIMENT ANALYSIS TAB ----------
        with tab_comments:
            st.markdown('<p style="margin-bottom: 15px;"></p>', unsafe_allow_html=True)
            
            # Settings for sentiment analysis
            with st.expander("Analysis Settings", expanded=True):
                max_comments = st.slider("Maximum comments to analyze", min_value=10, max_value=200, value=50, step=10)
            
            # Check if API key is available for YouTube
            analyze_sentiment_button = st.button("Analyze Sentiment", 
                    type='primary', 
                    use_container_width=True, 
                    key="sentiment_btn")

            # Sentiment labels with colors and emojis
            SENTIMENT_STYLES = {
                "positive": {"color": "#43A047", "emoji": "👍"},
                "neutral": {"color": "#9E9E9E", "emoji": "😐"},
                "negative": {"color": "#E53935", "emoji": "👎"},
            }

            if analyze_sentiment_button:
                # Extract video ID from URL
                video_url = st.session_state[f"yt_{st.session_state.youtube_key}"]
                video_id_match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', video_url)
                
                if not video_id_match:
                    st.error("Could not extract video ID from URL")
                else:
                    video_id = video_id_match.group(1)
                    
                    with st.spinner("Fetching and analyzing comments..."):
                        try:
                            # Fetch comments
                            comments = fetch_top_comments_from_youtube(video_id, max_comments=max_comments)
                            
                            if not comments:
                                st.warning("No comments found for this video.")
                            else:
                                st.success(f"Fetched {len(comments)} comments")
                                
                                # Clean texts: one for analysis, one for display
                                raw_texts = [c.get("text", "") for c in comments]
                                analysis_texts = [clean_text(t) for t in raw_texts]
                                display_texts = [clean_text_for_display(t) for t in raw_texts]
                                
                                # Filter out empty texts (keep indices aligned)
                                valid_data = [(disp, anal) for disp, anal in zip(display_texts, analysis_texts) if anal.strip()]
                                
                                if valid_data:
                                    display_texts, analysis_texts = zip(*valid_data)
                                    sentiments = predict_sentiment(list(analysis_texts))
                                    
                                    # Store display text with sentiments in session state
                                    st.session_state.comments_data = list(zip(display_texts, sentiments))
                                    
                        except Exception as e:
                            st.error(f"Error fetching comments: {str(e)}")
                            st.info("Make sure YOUTUBE_API_KEY is set in your environment variables.")
            
            # Display results if available
            if "comments_data" in st.session_state and st.session_state.comments_data:
                comments_data = st.session_state.comments_data
                total = len(comments_data)
                
                # Calculate emotion distribution
                emotion_counts = {}
                for _, e in comments_data:
                    label = e["label"]
                    emotion_counts[label] = emotion_counts.get(label, 0) + 1
                
                # Only show sentiments that were detected (count > 0), sorted by count
                detected_sentiments = [(e, c) for e, c in emotion_counts.items() if c > 0]
                detected_sentiments.sort(key=lambda x: x[1], reverse=True)
                
                # Display pie chart and table
                st.markdown("### Sentiment Distribution")
                
                col_chart, col_table = st.columns([2, 1])
                
                with col_chart:
                    # Prepare data for pie chart
                    labels = [f"{SENTIMENT_STYLES.get(e, {}).get('emoji', '❓')} {e.capitalize()}" for e, _ in detected_sentiments]
                    values = [c for _, c in detected_sentiments]
                    colors = [SENTIMENT_STYLES.get(e, {"color": "#9E9E9E"})["color"] for e, _ in detected_sentiments]
                    
                    fig = px.pie(
                        values=values,
                        names=labels,
                        color_discrete_sequence=colors,
                        hole=0.4  # Donut chart
                    )
                    fig.update_traces(
                        textposition='inside',
                        textinfo='percent',
                        hovertemplate='%{label}<br>Count: %{value}<br>Percent: %{percent}<extra></extra>'
                    )
                    fig.update_layout(
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=-0.3,
                            xanchor="center",
                            x=0.5,
                            font=dict(size=10)
                        ),
                        margin=dict(t=20, b=20, l=20, r=20),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white')
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col_table:
                    # Create table data
                    table_data = {
                        "Sentiment": [f"{SENTIMENT_STYLES.get(e, {}).get('emoji', '❓')} {e.capitalize()}" for e, _ in detected_sentiments],
                        "#": [c for _, c in detected_sentiments],
                        "%": [f"{100*c/total:.1f}%" for _, c in detected_sentiments]
                    }
                    df = pd.DataFrame(table_data)
                    st.dataframe(df, hide_index=True, use_container_width=True)
                
                # Display comments with sentiment
                st.markdown("### Analyzed Comments")
                
                # Filter options - only show detected sentiments
                filter_options = ["All"] + [e.capitalize() for e, _ in detected_sentiments]
                filter_sentiment = st.selectbox(
                    "Filter by sentiment:",
                    filter_options,
                    key="filter_sentiment"
                )
                
                import html as html_module
                
                for text, sentiment in comments_data:
                    if filter_sentiment != "All" and sentiment["label"].lower() != filter_sentiment.lower():
                        continue
                    
                    # Get style for this sentiment
                    style = SENTIMENT_STYLES.get(sentiment["label"], {"color": "#9E9E9E", "emoji": "❓"})
                    color = style["color"]
                    emoji = style["emoji"]
                    lang = sentiment.get("lang", "")
                    lang_flag = "🇷🇺" if lang == "ru" else "🇬🇧"
                    
                    # Escape HTML and convert newlines to <br> for display
                    safe_text = html_module.escape(text).replace('\n', '<br>')
                    
                    st.markdown(f'''
                        <div style="background-color: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid {color};">
                            <p style="margin: 0; color: #ffffff; font-size: 14px; white-space: pre-wrap;">{safe_text}</p>
                            <p style="margin: 5px 0 0 0; color: {color}; font-size: 12px;">{lang_flag} {emoji} {sentiment["label"].capitalize()} ({sentiment["score"]:.2%})</p>
                        </div>
                    ''', unsafe_allow_html=True)
        
        st.divider() 

        if st.button("Start again", type='secondary', icon=':material/refresh:'): 
            st.session_state.disabled_button = False
            st.session_state.youtube_key += 1
            st.session_state.condition_yt = False
            st.session_state.use_original_language = True
            st.session_state.language_settings_disabled = False
            clear_outputs()
            st.rerun()
            
  
if __name__ == "__main__":
    main()
