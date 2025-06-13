import streamlit as st
import praw
import google.generativeai as genai
from datetime import datetime
import time
from dotenv import load_dotenv
import os
import requests
import twitter_config

# Load .env variables
load_dotenv()
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash")

# Initialize Reddit
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

st.title("🌐 Reddit & Twitter Trend Summarizer")

# Inputs
query = st.text_input("🔍 Enter a topic to search:")
subreddit_name = st.text_input("📁 Subreddit (default: all):", value="all")
start_date = st.date_input("📅 Start Date")
end_date = st.date_input("📅 End Date")

if st.button("Fetch & Summarize"):
    start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
    end_ts = int(datetime.combine(end_date, datetime.min.time()).timestamp())

    combined_text = ""

    # --- Reddit ---
    st.subheader("📘 Reddit Results")
    subreddit = reddit.subreddit(subreddit_name)
    results = subreddit.search(query, sort="relevance", limit=10)

    filtered_posts = []
    for post in results:
        post_ts = int(post.created_utc)
        if start_ts <= post_ts <= end_ts:
            filtered_posts.append(post)

    if not filtered_posts:
        if list(results):
            st.info("Posts were found, but none matched the selected date range.")
        else:
            st.warning("No Reddit posts found for this topic.")
    else:
        for post in filtered_posts:
            st.subheader(post.title)
            st.caption(f"r/{post.subreddit} • Score: {post.score}")
            st.write(post.url)
            try:
                post.comments.replace_more(limit=0)
                top_comments = post.comments.list()[:5]
                st.markdown("**Top Comments:**")
                for i, comment in enumerate(top_comments, 1):
                    text = comment.body.strip()[:300]
                    st.markdown(f"{i}. {text}")
                    combined_text += f"Reddit Post: {post.title}\nComment: {text}\n"
            except Exception as e:
                st.error(f"Error fetching comments: {e}")

    # --- Twitter ---
    st.subheader("🐦 Twitter Results")
    def fetch_tweets(query, max_results=10):
        headers = {"Authorization": f"Bearer {twitter_config.bearer_token}"}
        params = {
            "query": f"{query} -is:retweet",
            "max_results": max(10, min(max_results, 100)),
            "tweet.fields": "author_id,created_at"
        }
        url = "https://api.twitter.com/2/tweets/search/recent"
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            st.error(f"❌ Twitter error: {response.status_code} - {response.text}")
            return []
        return response.json().get("data", [])

    tweets = fetch_tweets(query, max_results=10)

    if not tweets:
        st.warning("No tweets found.")
    else:
        for i, tweet in enumerate(tweets, 1):
            st.markdown(f"**Tweet #{i}**")
            st.markdown(f"🕒 {tweet['created_at']}")
            st.markdown(f"{tweet['text']}")
            combined_text += f"Tweet: {tweet['text']}\n"

    # --- Gemini Summary ---
    st.subheader("🧠 Summary (AI-Generated)")
    with st.spinner("Creating summary with Gemini..."):
        try:
            safe_text = combined_text[:3000]
            prompt = (
                "Summarize the following Reddit and Twitter content using bullet points. "
                "Highlight trending topics, common opinions, and anything noteworthy in a professional yet creative tone:\n"
                f"{safe_text}"
            )
            response = model.generate_content(prompt)
            st.success("Here's the summary:")
            st.markdown(response.text)
        except Exception as e:
            if "429" in str(e):
                st.warning("Rate limit hit. Waiting 60 seconds...")
                time.sleep(60)
                try:
                    response = model.generate_content(prompt)
                    st.success("Here's the summary:")
                    st.markdown(response.text)
                except Exception as e2:
                    st.error(f"Retry failed: {e2}")
            else:
                st.error(f"Gemini API error: {e}")
