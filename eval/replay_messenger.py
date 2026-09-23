"""
Replay real customer questions from the Facebook page through the CURRENT bot.

1. Downloads all page conversations via the Graph API (cached locally).
2. Picks the UNIQUE customer questions (duplicates like "المصاريف كام" are
   tested once), skipping non-questions ("شكراً", "تمام", emojis...).
   Questions the old bot answered with "مش متوفرة" come first, then the most
   frequently asked ones.
3. Sends each question to the bot with the real conversation history that
   came before it, and writes a CSV (opens in Excel): old reply vs. new reply.

NOTHING is sent to customers: Facebook sending and Redis are replaced with
in-memory fakes.

GROQ QUOTA PROTECTION
Groq limits are shared by everything that uses the same API key, including
the live bot. To protect real customers:
  - Put a separate key in .env as EVAL_GROQ_API_KEY → the script uses it.
  - Without it, the script refuses to call Groq unless --allow-production-key.
  - --max-questions and --token-budget are hard caps (defaults: 30 / 100k).

Usage (from the project root):
    python eval/replay_messenger.py --download-only        # only fetch conversations (no Groq)
    python eval/replay_messenger.py --stats                # how many unique questions (no Groq)
    python eval/replay_messenger.py --max-questions 30      # replay 30 questions
    python eval/replay_messenger.py --report-only          # rebuild the CSV only
    python eval/replay_messenger.py --only "بكام"          # re-test specific question(s)

Results are saved as they are produced; running again continues with the
questions that were not tested yet.
"""

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Must run BEFORE importing api.config, which reads GROQ_API_KEY at import time.
load_dotenv(ROOT / ".env")
USING_EVAL_KEY = bool(os.environ.get("EVAL_GROQ_API_KEY"))
if USING_EVAL_KEY:
    os.environ["GROQ_API_KEY"] = os.environ["EVAL_GROQ_API_KEY"]

from api.config import PAGE_ACCESS_TOKEN  # noqa: E402
import api.services.llm_service as llm  # noqa: E402
import api.services.facebook_service as fb  # noqa: E402
from api.services.quick_rules import (  # noqa: E402
    UNKNOWN_INFO_REPLY, PARTIAL_INFO_REPLY, JOB_INQUIRY_REPLY, NO_ANSWER_REPLY,
    ACADEMY_REPLY, normalize_arabic,
)

GRAPH = "https://graph.facebook.com/v21.0"
OUT_DIR = ROOT / "eval" / "output"
CONVERSATIONS_FILE = OUT_DIR / "conversations.json"
RESULTS_FILE = OUT_DIR / "replay_results.jsonl"
CSV_FILE = OUT_DIR / "replay_report.csv"


# ─── 1. Download conversations ───────────────────────────────────────────────

def graph_get_all(client: httpx.Client, url: str, params: dict) -> list:
    """Follows Graph API pagination and returns all items."""
    items = []
    while url:
        res = client.get(url, params=params)
        data = res.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message"))
        items.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = None  # "next" URL already contains all params
    return items


def download_conversations() -> dict:
    with httpx.Client(timeout=30.0) as client:
        # Conversations and their messages come together, 25 conversations per request.
        convs = []
        url = f"{GRAPH}/me/conversations"
        params = {
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "id,updated_time,participants,messages.limit(100){message,from,created_time}",
            "limit": 25,
        }
        while url:
            data = client.get(url, params=params).json()
            if "error" in data:
                raise RuntimeError(data["error"].get("message"))
            convs.extend(data.get("data", []))
            print(f"   📥 {len(convs)} conversations downloaded", flush=True)
            url, params = data.get("paging", {}).get("next"), None

        # The token can't read /me, so the page id is the participant present in every conversation.
        participant_counts = Counter(
            p["id"] for c in convs for p in c.get("participants", {}).get("data", [])
        )
        page_id = participant_counts.most_common(1)[0][0]

        result = []
        for conv in convs:
            msgs = conv.get("messages", {}).get("data", [])
            # Rare: conversation longer than 100 messages → fetch the remaining pages.
            next_url = conv.get("messages", {}).get("paging", {}).get("next")
            if next_url:
                msgs += graph_get_all(client, next_url, None)
            msgs.reverse()  # API returns newest first
            result.append({
                "id": conv["id"],
                "updated_time": conv["updated_time"],
                "messages": [
                    {
                        "text": (m.get("message") or "").strip(),
                        "from_page": m.get("from", {}).get("id") == page_id,
                        "time": m.get("created_time"),
                    }
                    for m in msgs
                ],
            })

    data = {"page_id": page_id, "conversations": result}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CONVERSATIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"💾 Saved to {CONVERSATIONS_FILE}")
    return data


# ─── 2. Pick unique questions ────────────────────────────────────────────────

NOT_QUESTIONS = {
    normalize_arabic(w) for w in (
        "شكرا", "شكراً", "متشكر", "متشكرة", "مرسي", "تمام", "ماشي", "حاضر", "اوك", "اوكي",
        "ok", "okay", "thanks", "thank you", "تسلم", "تسلمي", "جزاك الله خيرا", "السلام عليكم",
        "وعليكم السلام", "اهلا", "هاي", "hi", "hello", "get started", "بدء الاستخدام", "يعني",
    )
}


def question_key(text: str) -> str:
    """Normalized text used to detect duplicate questions."""
    text = normalize_arabic(text)
    text = re.sub(r"[^\w\s]", " ", text)  # drop punctuation and emojis
    return re.sub(r"\s+", " ", text).strip()


def build_history(msgs: list, idx: int) -> list:
    """The real conversation before message idx, in the bot's history format."""
    history = []
    for m in msgs[:idx]:
        if not m["text"]:
            continue  # buttons / attachments
        role = "assistant" if m["from_page"] else "user"
        if history and history[-1]["role"] == role:
            history[-1]["content"] += "\n\n" + m["text"]
        else:
            history.append({"role": role, "content": m["text"]})
    return history[-6:]


def pick_questions(conversations: list) -> list:
    # Newest conversations first, so the kept example of each question is recent.
    conversations = sorted(conversations, key=lambda c: c["updated_time"], reverse=True)
    by_key: dict[str, dict] = {}
    for conv in conversations:
        msgs = conv["messages"]
        for idx, msg in enumerate(msgs):
            if msg["from_page"] or not msg["text"]:
                continue
            key = question_key(msg["text"])
            if len(key) < 3 or key in NOT_QUESTIONS:
                continue
            if key in by_key:
                by_key[key]["times_asked"] += 1
                continue

            old_reply = []
            for nxt in msgs[idx + 1:]:
                if not nxt["from_page"]:
                    break
                old_reply.append(nxt["text"] or "[زرار / مرفق]")
            old_reply = "\n\n".join(old_reply)

            by_key[key] = {
                "key": key,
                "question": msg["text"],
                "times_asked": 1,
                "time": msg["time"],
                "conversation": conv["id"],
                "old_reply": old_reply,
                "old_unknown": "مش متوفرة" in old_reply or "مش متوفره" in old_reply,
                "history": build_history(msgs, idx),
            }

    # Old "unknown" answers first, then the most frequent questions.
    return sorted(by_key.values(), key=lambda q: (not q["old_unknown"], -q["times_asked"]))


# ─── 3. Replay through the bot ───────────────────────────────────────────────

def classify_reply(sent: list) -> str:
    texts = [s["text"] for s in sent]
    if not texts:
        return "no_reply"
    if JOB_INQUIRY_REPLY in texts:
        return "job"
    if NO_ANSWER_REPLY in texts:
        return "no_answer"
    if ACADEMY_REPLY in texts:
        return "academy"
    if UNKNOWN_INFO_REPLY in texts:
        return "unknown"
    if PARTIAL_INFO_REPLY in texts:
        return "partial"
    if any("عطل" in t or "خطأ مؤقت" in t for t in texts):
        return "error"
    return "answered"


def load_results() -> list:
    if not RESULTS_FILE.exists():
        return []
    with RESULTS_FILE.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


async def replay(questions: list, max_questions: int, token_budget: int, delay: float, only: list = None):
    sent: list = []
    intents_seen: list = []
    current_history: list = []
    tokens = {"used": 0}

    async def fake_send(sender_id, text, quick_replies=None, call_admin=False):
        sent.append({"text": text, "call_button": call_admin})

    original_classify = llm.classify_intent

    async def recording_classify(message):
        intents = await original_classify(message)
        intents_seen.append(intents)
        return intents

    # Count the real Groq tokens used, to enforce the budget.
    original_post = httpx.AsyncClient.post

    async def counting_post(self, url, *args, **kwargs):
        res = await original_post(self, url, *args, **kwargs)
        if "groq.com" in str(url) and res.status_code == 200:
            tokens["used"] += res.json().get("usage", {}).get("total_tokens", 0)
        return res

    # Never touch real customers or the production Redis history.
    llm.send_fb_message = fake_send
    fb.send_fb_message = fake_send
    llm.get_user_history = lambda sid: list(current_history)
    llm.save_user_history = lambda sid, msgs: None
    llm.classify_intent = recording_classify
    httpx.AsyncClient.post = counting_post

    if only:
        # Re-test specific questions: drop their previous results first.
        wanted = {question_key(t) for t in only}
        kept = [r for r in load_results() if r["key"] not in wanted]
        RESULTS_FILE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
        questions = [q for q in questions if q["key"] in wanted]

    done = {r["key"] for r in load_results()}
    todo = [q for q in questions if q["key"] not in done][:max_questions]
    print(f"▶️ Replaying {len(todo)} questions ({len(done)} already done, "
          f"{len(questions)} unique in total). Token budget: {token_budget:,}\n", flush=True)

    with RESULTS_FILE.open("a", encoding="utf-8") as out:
        for n, q in enumerate(todo, 1):
            if tokens["used"] >= token_budget:
                print(f"\n🛑 Token budget reached ({tokens['used']:,}). Stopping.")
                break

            sent.clear()
            intents_seen.clear()
            current_history[:] = q["history"]
            before = tokens["used"]
            try:
                await llm.process_and_reply("replay", q["question"])
            except Exception as e:
                sent.append({"text": f"[EXCEPTION] {e}", "call_button": False})

            row = {k: v for k, v in q.items() if k != "history"}
            row.update({
                "new_reply": "\n\n".join(s["text"] for s in sent),
                "call_button": any(s["call_button"] for s in sent),
                "kind": classify_reply(sent),
                "intents": ",".join(intents_seen[0]) if intents_seen else "(rule)",
                "tokens": tokens["used"] - before,
            })
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"[{n}/{len(todo)}] {row['kind']:9} x{q['times_asked']:<3} "
                  f"({row['tokens']} tok) | {q['question'][:60]}", flush=True)
            if row["intents"] != "(rule)":
                await asyncio.sleep(delay)

    httpx.AsyncClient.post = original_post
    print(f"\n🔢 Groq tokens used in this run: {tokens['used']:,}")


# ─── 4. Report ───────────────────────────────────────────────────────────────

KIND_ORDER = {"unknown": 0, "partial": 1, "error": 2, "no_reply": 3, "job": 4, "no_answer": 5, "academy": 6, "answered": 7}


def write_report():
    rows = load_results()
    if not rows:
        print("No results yet.")
        return
    rows.sort(key=lambda r: (KIND_ORDER.get(r["kind"], 9), -r["times_asked"]))

    # utf-8-sig so Excel shows Arabic correctly
    with CSV_FILE.open("w", encoding="utf-8-sig", newline="") as f:
        cols = ["question", "times_asked", "kind", "new_reply", "old_reply", "intents", "time", "conversation"]
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    kinds = Counter(r["kind"] for r in rows)
    print(f"\n📊 {len(rows)} unique questions tested:")
    for kind, n in kinds.most_common():
        print(f"   {kind:10} {n}")
    print(f"\n📄 Report: {CSV_FILE}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="re-download conversations from Facebook")
    parser.add_argument("--download-only", action="store_true", help="only download conversations (no Groq)")
    parser.add_argument("--stats", action="store_true", help="show question counts only (no Groq)")
    parser.add_argument("--report-only", action="store_true", help="only rebuild the CSV from saved results")
    parser.add_argument("--max-questions", type=int, default=30, help="max questions to replay in this run")
    parser.add_argument("--token-budget", type=int, default=100_000, help="stop after this many Groq tokens")
    parser.add_argument("--delay", type=float, default=30.0, help="seconds between questions")
    parser.add_argument("--only", action="append",
                        help="re-test this exact question (repeatable); replaces its previous result")
    parser.add_argument("--allow-production-key", action="store_true",
                        help="allow using the live bot's GROQ_API_KEY (shares its quota!)")
    args = parser.parse_args()

    if args.report_only:
        write_report()
        return

    if args.refresh or not CONVERSATIONS_FILE.exists():
        data = download_conversations()
    else:
        data = json.loads(CONVERSATIONS_FILE.read_text(encoding="utf-8"))
    if args.download_only:
        return

    questions = pick_questions(data["conversations"])
    if args.stats:
        total = sum(q["times_asked"] for q in questions)
        unknown = sum(1 for q in questions if q["old_unknown"])
        print(f"💬 {total} customer questions → {len(questions)} unique")
        print(f"❓ {unknown} unique questions the old bot answered with 'مش متوفرة'")
        print("\n🔝 Most asked:")
        for q in sorted(questions, key=lambda q: -q["times_asked"])[:25]:
            print(f"   x{q['times_asked']:<4} {q['question'][:80]}")
        return

    if not USING_EVAL_KEY and not args.allow_production_key:
        sys.exit(
            "⛔ No EVAL_GROQ_API_KEY in .env.\n"
            "   Using the live bot's key would consume the same Groq quota real customers need.\n"
            "   Add EVAL_GROQ_API_KEY to .env, or pass --allow-production-key (run at night, small --max-questions)."
        )

    asyncio.run(replay(questions, args.max_questions, args.token_budget, args.delay, args.only))
    write_report()


if __name__ == "__main__":
    main()
