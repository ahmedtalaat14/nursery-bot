from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    """Privacy Policy page endpoint."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Privacy Policy - Adam's & Elbaraa Nursery</title>
    <style>
        :root {
            --primary: #0f766e;
            --primary-dark: #0d9488;
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.6;
            margin: 0;
            padding: 2rem 1rem;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: var(--card-bg);
            padding: 2.5rem;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            border: 1px solid var(--border);
        }
        h1 {
            color: var(--primary-dark);
            margin-top: 0;
            border-bottom: 2px solid var(--border);
            padding-bottom: 0.5rem;
        }
        h2 {
            color: #38bdf8;
            margin-top: 1.8rem;
        }
        p, li {
            color: var(--text-muted);
            font-size: 1rem;
        }
        ul {
            padding-left: 1.2rem;
        }
        .effective-date {
            font-style: italic;
            color: var(--primary-dark);
            margin-bottom: 2rem;
        }
        a {
            color: #38bdf8;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Privacy Policy</h1>
        <p class="effective-date">Effective Date: August 2026</p>

        <p>This Privacy Policy outlines how <strong>Adam's & Elbaraa Nursery (حضانة آدمز والبراء)</strong> collects, processes, and protects user information when you interact with our Facebook Messenger Assistant.</p>

        <h2>1. Information We Collect</h2>
        <p>When you message our Facebook page, we process minimal data provided via the official Meta Graph API:</p>
        <ul>
            <li>Your Facebook Page-Scoped User ID (PSID)</li>
            <li>Your Facebook Profile Name (if made accessible by Meta)</li>
            <li>The text messages and inquiries you send to the assistant</li>
        </ul>

        <h2>2. How Information is Used</h2>
        <p>We use the processed data solely for the following purposes:</p>
        <ul>
            <li>Providing instant automated customer service responses regarding nursery fees, working hours, location, curriculum, and admissions.</li>
            <li>Maintaining temporary conversation context to ensure meaningful multi-turn dialogue.</li>
        </ul>

        <h2>3. Data Sharing & Third Parties</h2>
        <p>We do NOT sell, lease, trade, or share your personal data with any third parties for advertising or commercial purposes. Information processing relies strictly on secure cloud APIs (Groq AI & Upstash Redis) to generate real-time automated responses.</p>

        <h2>4. Data Retention & Deletion</h2>
        <p>Conversation history is retained in our secure Redis cache for a maximum of 24 hours to support context continuity, after which it is automatically purged. Users may clear their chat directly in Facebook Messenger or contact management to request complete data deletion.</p>

        <h2>5. Contact Us</h2>
        <p>If you have any questions regarding this Privacy Policy or wish to contact Adam's & Elbaraa Nursery administration, please visit our official website at <a href="https://adams-rouge.vercel.app" target="_blank">https://adams-rouge.vercel.app</a>.</p>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content, status_code=200)
