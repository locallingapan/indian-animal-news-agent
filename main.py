import os
import json
import urllib.parse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import feedparser
from google import genai
from google.genai import types

# Configured via environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")       # Your Gmail address
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD") # App password
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")   # Destination email

client = genai.Client(api_key=GEMINI_API_KEY)


def fetch_google_news_stories(query: str, max_results: int = 15) -> list[dict]:
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    feed = feedparser.parse(rss_url)
    stories = []
    
    for entry in feed.entries[:max_results]:
        stories.append({
            "title": getattr(entry, "title", "No Title"),
            "url": getattr(entry, "link", ""),
            "published": getattr(entry, "published", "Recently"),
            "snippet": getattr(entry, "summary", "")
        })
    return stories


def curate_stories(raw_stories: list[dict]) -> list[dict]:
    prompt = f"""
    You are an expert wildlife news curator focusing on animal stories in India.
    Evaluate the provided news stories and return ONLY a JSON list of qualifying stories.

    STRICT EXCLUSION RULES:
    - Automatically set score to 0 for routine domestic animal or pet news (dogs, cats, cattle, adoptions, pet shops, farm care).
    - EXCEPTION: Include domestic animal stories ONLY IF their path crosses with wild animals or wildlife conservation (e.g., guard dogs protecting livestock from leopards, feral dogs threatening wild birds, human-wildlife conflict).

    SCORING CRITERIA (1 to 10):
    - Score >= 7: High impact wildlife rescues, human-wildlife interactions, rare species, or conservation wins in India.
    - Omit any story with a score lower than 7.

    Input Stories:
    {json.dumps(raw_stories)}

    Output Format (JSON List ONLY):
    [
      {{
        "title": "Clean, engaging headline",
        "score": 8,
        "location": "State/City in India",
        "reasoning": "Why it qualified (especially if wild/domestic interaction occurred)",
        "summary": "2-3 sentence concise summary of what happened.",
        "url": "original_url"
      }}
    ]
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)


def send_email_digest(curated_stories: list[dict]):
    if not curated_stories:
        print("No qualifying stories found today. Skipping email.")
        return

    html_items = ""
    for story in curated_stories:
        html_items += f"""
        <div style="margin-bottom: 24px; padding: 16px; border-left: 4px solid #2e7d32; background-color: #f9fbf9;">
            <h2 style="margin: 0 0 8px 0; color: #1b5e20; font-size: 18px;">
                🐾 {story['title']} <span style="font-size: 14px; color: #555;">(Score: {story['score']}/10)</span>
            </h2>
            <p style="margin: 4px 0; font-size: 13px; color: #666;"><strong>📍 Location:</strong> {story['location']}</p>
            <p style="margin: 8px 0; font-size: 14px; color: #333; line-height: 1.5;">{story['summary']}</p>
            <p style="margin: 4px 0; font-size: 12px; color: #777;"><em>💡 Why it passed: {story['reasoning']}</em></p>
            <p style="margin-top: 10px;">
                <a href="{story['url']}" style="background-color: #2e7d32; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 12px; display: inline-block;">Read Full Story →</a>
            </p>
        </div>
        """

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #1b5e20; border-bottom: 2px solid #2e7d32; padding-bottom: 10px;">
            🌿 Daily Wildlife & Animal Stories Digest (India)
        </h1>
        <p style="color: #666; font-size: 14px;">Here are today's top curated stories regarding wildlife, conservation, and animal interactions in India:</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        {html_items}
        <footer style="margin-top: 30px; font-size: 11px; color: #999; text-align: center;">
            Automated by your Gemini AI Agent
        </footer>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🐾 Daily Animal & Wildlife Stories Digest"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"Email digest successfully sent to {RECEIVER_EMAIL}!")
    except Exception as e:
        print(f"Failed to send email: {e}")


if __name__ == "__main__":
    search_query = '("wildlife" OR "animal rescue" OR "human animal conflict" OR "conservation") India'
    
    print("1. Fetching raw news items...")
    raw_news = fetch_google_news_stories(query=search_query, max_results=15)
    
    print(f"2. Curating {len(raw_news)} raw items with Gemini...")
    curated = curate_stories(raw_news)
    
    print(f"3. Found {len(curated)} high-scoring story/stories. Sending email...")
    send_email_digest(curated)