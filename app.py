import os
import sqlite3

from flask import Flask, render_template, request, redirect
from google import genai


# =========================================================
# GEMINI AI SETUP
# =========================================================

api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    client = genai.Client(api_key=api_key)
else:
    client = None


# =========================================================
# FLASK SETUP
# =========================================================

app = Flask(__name__)

DATABASE = "content_agent.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def initialize_database():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            topic TEXT NOT NULL,
            platform TEXT NOT NULL,
            content_type TEXT NOT NULL,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            reach INTEGER DEFAULT 1
        )
    """)

    # Add sample data only if database is empty
    count = conn.execute(
        "SELECT COUNT(*) FROM content"
    ).fetchone()[0]

    if count == 0:

        sample_data = [
            (
                "AI Trends 2026",
                "AI",
                "LinkedIn",
                "Carousel",
                820,
                95,
                120,
                12000
            ),
            (
                "AI Productivity Tips",
                "AI",
                "LinkedIn",
                "Video",
                950,
                120,
                150,
                14000
            ),
            (
                "Company Update",
                "Company",
                "LinkedIn",
                "Image",
                210,
                20,
                12,
                9000
            ),
            (
                "Marketing Tips",
                "Marketing",
                "Instagram",
                "Carousel",
                650,
                70,
                80,
                11000
            ),
            (
                "Product Announcement",
                "Product",
                "LinkedIn",
                "Image",
                180,
                15,
                8,
                8500
            ),
            (
                "Future of AI",
                "AI",
                "LinkedIn",
                "Article",
                730,
                85,
                100,
                12500
            ),
            (
                "Career with AI",
                "Career",
                "Instagram",
                "Reel",
                600,
                90,
                75,
                10000
            ),
            (
                "Tech News",
                "Technology",
                "LinkedIn",
                "Post",
                450,
                45,
                50,
                9500
            )
        ]

        conn.executemany("""
            INSERT INTO content
            (
                title,
                topic,
                platform,
                content_type,
                likes,
                comments,
                shares,
                reach
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_data)

    conn.commit()
    conn.close()


# =========================================================
# GET ALL CONTENT
# =========================================================

def get_content():

    conn = get_db()

    rows = conn.execute("""
        SELECT *,
        ROUND(
            (
                (likes + comments + shares) * 100.0
            ) /
            CASE
                WHEN reach = 0 THEN 1
                ELSE reach
            END,
            2
        ) AS engagement

        FROM content

        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows


# =========================================================
# GET STATISTICS
# =========================================================

def get_statistics():

    conn = get_db()

    total_posts = conn.execute(
        "SELECT COUNT(*) FROM content"
    ).fetchone()[0]

    total_reach = conn.execute(
        "SELECT COALESCE(SUM(reach), 0) FROM content"
    ).fetchone()[0]

    total_engagement = conn.execute("""
        SELECT COALESCE(
            SUM(likes + comments + shares),
            0
        )
        FROM content
    """).fetchone()[0]

    avg_engagement = conn.execute("""
        SELECT AVG(
            (
                (likes + comments + shares) * 100.0
            ) /
            CASE
                WHEN reach = 0 THEN 1
                ELSE reach
            END
        )
        FROM content
    """).fetchone()[0]

    top_topic = conn.execute("""
        SELECT
            topic,

            AVG(
                (
                    (likes + comments + shares) * 100.0
                ) /
                CASE
                    WHEN reach = 0 THEN 1
                    ELSE reach
                END
            ) AS score

        FROM content

        GROUP BY topic

        ORDER BY score DESC

        LIMIT 1
    """).fetchone()

    conn.close()

    return {
        "total_posts": total_posts,
        "total_reach": total_reach,
        "total_engagement": total_engagement,
        "avg_engagement": round(
            avg_engagement or 0,
            2
        ),
        "top_topic": (
            top_topic["topic"]
            if top_topic
            else "N/A"
        )
    }


# =========================================================
# FIND CONTENT GAPS
# =========================================================

def find_content_gaps():

    conn = get_db()

    topics = conn.execute("""
        SELECT
            topic,
            COUNT(*) AS count

        FROM content

        GROUP BY topic

        ORDER BY count DESC
    """).fetchall()

    conn.close()

    covered_topics = {
        row["topic"]
        for row in topics
    }

    possible_topics = {
        "AI",
        "Marketing",
        "Technology",
        "Career",
        "AI Ethics",
        "AI Productivity",
        "Leadership",
        "Innovation",
        "Industry Trends"
    }

    gaps = list(
        possible_topics - covered_topics
    )

    return gaps[:5]


# =========================================================
# BASIC CONTENT RECOMMENDATION
# =========================================================

def generate_recommendation():

    conn = get_db()

    top_post = conn.execute("""
        SELECT
            title,
            topic,

            (
                (likes + comments + shares) * 100.0
            ) /
            CASE
                WHEN reach = 0 THEN 1
                ELSE reach
            END AS engagement

        FROM content

        ORDER BY engagement DESC

        LIMIT 1
    """).fetchone()

    conn.close()

    gaps = find_content_gaps()

    if top_post:

        topic = top_post["topic"]
        best_post = top_post["title"]

    else:

        topic = "AI"
        best_post = "N/A"

    if gaps:

        gap = gaps[0]

    else:

        gap = "new industry trends"

    return (
        f"Your strongest content is "
        f"'{best_post}' around {topic}. "

        f"Based on your content history, "
        f"consider creating content about "
        f"'{gap}'. "

        f"Try an educational carousel or "
        f"short video and measure its engagement."
    )


# =========================================================
# AI CONTENT STRATEGY AGENT
# =========================================================

def ask_content_agent(user_question):

    content = get_content()

    stats = get_statistics()

    gaps = find_content_gaps()

    # -----------------------------------------------------
    # Build content memory
    # -----------------------------------------------------

    memory = ""

    for item in content:

        memory += f"""
Title: {item['title']}
Topic: {item['topic']}
Platform: {item['platform']}
Format: {item['content_type']}
Engagement: {item['engagement']}%
Likes: {item['likes']}
Comments: {item['comments']}
Shares: {item['shares']}
Reach: {item['reach']}
--------------------------------
"""

    # -----------------------------------------------------
    # Gemini Prompt
    # -----------------------------------------------------

    prompt = f"""
You are a Content Strategy AI Agent.

Your job is to help a marketing team create
better content using historical content data.

IMPORTANT RULES:

1. Use the provided content history.
2. Do not invent historical performance data.
3. Clearly separate historical facts from your recommendations.
4. Give practical and easy-to-understand advice.
5. If there is not enough historical data, say so.

CONTENT HISTORY:

{memory}


CONTENT STATISTICS:

Total posts:
{stats['total_posts']}

Total reach:
{stats['total_reach']}

Average engagement:
{stats['avg_engagement']}%

Top topic:
{stats['top_topic']}


CONTENT GAPS:

{', '.join(gaps)}


USER QUESTION:

{user_question}


Answer the user's question.

When appropriate, explain:

1. What the historical data says
2. What content performed well
3. What content is missing
4. What you recommend
5. The next practical step

Keep the answer clear and easy to understand.
"""


    # -----------------------------------------------------
    # Check Gemini connection
    # -----------------------------------------------------

    if not client:

        return (
            "Gemini API is not connected.\n\n"
            "Please set the GEMINI_API_KEY "
            "environment variable and restart Flask."
        )


    # -----------------------------------------------------
    # Call Gemini
    # -----------------------------------------------------

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:

        return f"AI Error: {str(e)}"


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    content = get_content()

    stats = get_statistics()

    gaps = find_content_gaps()

    recommendation = generate_recommendation()

    return render_template(
        "index.html",
        content=content,
        stats=stats,
        gaps=gaps,
        recommendation=recommendation
    )


# =========================================================
# ADD CONTENT
# =========================================================

@app.route("/add", methods=["POST"])
def add_content():

    title = request.form["title"]

    topic = request.form["topic"]

    platform = request.form["platform"]

    content_type = request.form["content_type"]

    likes = int(
        request.form.get("likes", 0) or 0
    )

    comments = int(
        request.form.get("comments", 0) or 0
    )

    shares = int(
        request.form.get("shares", 0) or 0
    )

    reach = int(
        request.form.get("reach", 1) or 1
    )

    # Prevent division by zero
    if reach <= 0:
        reach = 1

    conn = get_db()

    conn.execute("""
        INSERT INTO content
        (
            title,
            topic,
            platform,
            content_type,
            likes,
            comments,
            shares,
            reach
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        topic,
        platform,
        content_type,
        likes,
        comments,
        shares,
        reach
    ))

    conn.commit()

    conn.close()

    return redirect("/")


# =========================================================
# ASK AI
# =========================================================

@app.route("/ask", methods=["POST"])
def ask():

    question = request.form.get(
        "question",
        ""
    ).strip()

    if not question:

        answer = "Please enter a question."

    else:

        answer = ask_content_agent(
            question
        )

    content = get_content()

    stats = get_statistics()

    gaps = find_content_gaps()

    recommendation = generate_recommendation()

    return render_template(
        "index.html",
        content=content,
        stats=stats,
        gaps=gaps,
        recommendation=recommendation,
        ai_answer=answer
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    initialize_database()

    print("----------------------------------------")
    print("Content Strategy Agent is running")
    print("Open: http://127.0.0.1:5000")
    print("----------------------------------------")

    app.run(
        debug=True
    )