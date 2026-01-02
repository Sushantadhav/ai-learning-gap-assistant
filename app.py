import streamlit as st
from groq import Groq
import os
from dotenv import load_dotenv
import datetime
import json
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# ---------------------------------
#  LOAD API KEY
# ---------------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.error("Groq API key missing. Add it in .env or Streamlit Secrets.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)


# ---------------------------------
#  LOCAL SESSION STORAGE (JSON)
# ---------------------------------
DATA_FILE = "student_sessions.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)


def load_sessions():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_session(entry):
    data = load_sessions()
    data.append(entry)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ---------------------------------
#  SUBJECT PRESETS
# ---------------------------------
SUBJECT_PRESETS = {
    "General": "Explain simply using relatable daily-life examples.",
    "Math": "Explain step-by-step with conceptual breakdown.",
    "Science": "Explain like a real-world process with analogies.",
    "Computer Science": "Explain concept first, then small example.",
    "Economics": "Explain with real-life decision-making scenarios."
}

SYSTEM_PROMPT = """
You are an AI-Powered Learning Gap Assistant.

Focus on conceptual clarity and understanding.
Avoid cheating or direct exam-type solutions.

Always respond in this structure:

1) Concept Explanation
2) Real-World Example
3) Key Points Summary (3–5 bullets)
4) Common Misconceptions
5) Quick Practice Questions (no answers)
6) Ask if student wants simpler explanation or more examples
"""


# ---------------------------------
#  SESSION STATE
# ---------------------------------
for k, v in {
    "chat_history": [],
    "meta_log": [],
    "feedback_log": [],
    "last_answer": None,
    "session_topic": ""
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ---------------------------------
#  AI RESPONSE FUNCTION
# ---------------------------------
def generate_response(question, subject, depth, style, mode="normal"):

    refinement = {
        "simpler": "Provide a simpler explanation than before.",
        "more_examples": "Provide more real-world examples and analogies."
    }.get(mode, "")

    user_prompt = f"""
Session Topic: {st.session_state.session_topic}

Subject: {subject}
Depth: {depth}
Style: {style}

Guidance:
{SUBJECT_PRESETS.get(subject, "")}

Refinement Mode:
{refinement}

Student Question:
{question}
"""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for speaker, msg in st.session_state.chat_history:
        role = "user" if speaker == "Student" else "assistant"
        messages.append({"role": role, "content": msg})

    messages.append({"role": "user", "content": user_prompt})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )

    answer = response.choices[0].message.content

    st.session_state.chat_history.append(("Student", question))
    st.session_state.chat_history.append(("AI Assistant", answer))

    st.session_state.last_answer = answer

    entry = {
        "timestamp": str(datetime.datetime.now()),
        "topic": st.session_state.session_topic,
        "subject": subject,
        "depth": depth,
        "style": style,
        "question": question,
        "response": answer
    }

    st.session_state.meta_log.append(entry)
    save_session(entry)

    return answer


# ---------------------------------
#  LEARNING SUMMARY TEXT
# ---------------------------------
def generate_summary():
    if not st.session_state.meta_log:
        return "No questions asked yet."

    questions = [x["question"] for x in st.session_state.meta_log]
    subjects = {x["subject"] for x in st.session_state.meta_log}

    text = f"""
AI Learning Session Summary

Session Topic: {st.session_state.session_topic}
Date: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}

Total Questions: {len(questions)}

Subjects Covered:
- """ + "\n- ".join(subjects) + """

Questions Asked:
"""

    for q in questions:
        text += f"• {q}\n"

    text += """
Reflection Notes:
• Identify confusing areas
• Try to explain concepts yourself
• Ask follow-up questions if needed
"""

    return text


# ---------------------------------
#  PDF EXPORT
# ---------------------------------
def export_pdf():

    filename = "learning_summary.pdf"
    c = canvas.Canvas(filename, pagesize=letter)

    lines = generate_summary().split("\n")

    y = 750
    for line in lines:
        c.drawString(50, y, line)
        y -= 14
        if y < 50:
            c.showPage()
            y = 750

    c.save()
    return filename


# ---------------------------------
#  UI HEADER
# ---------------------------------
st.title("AI Learning Gap Assistant (Student Learning Support)")
st.caption("Concept-focused AI explanation assistant aligned with SDG-4 Quality Education")

st.divider()


# ---------------------------------
#  SESSION TOPIC
# ---------------------------------
st.session_state.session_topic = st.text_input(
    "Session Topic (optional)",
    value=st.session_state.session_topic
)


# ---------------------------------
#  RESET SESSION
# ---------------------------------
if st.button("Start New Session"):
    st.session_state.chat_history = []
    st.session_state.meta_log = []
    st.session_state.feedback_log = []
    st.session_state.last_answer = None
    st.success("Session cleared — start fresh.")


# ---------------------------------
#  INPUT CONTROLS
# ---------------------------------
subject = st.selectbox("Select Subject", ["General", "Math", "Science", "Computer Science", "Economics"])
depth = st.selectbox("Learning Depth", ["Basic", "Intermediate", "Detailed"])
style = st.selectbox("Explanation Style", ["Simple", "Step-by-Step", "Concept Breakdown"])

question = st.chat_input("Ask your question...")


if question:
    generate_response(question, subject, depth, style)


# ---------------------------------
#  CHAT UI
# ---------------------------------
st.divider()
st.subheader("Conversation")

for speaker, msg in st.session_state.chat_history:
    with st.chat_message("user" if speaker == "Student" else "assistant"):
        st.markdown(msg)


# ---------------------------------
#  UNDERSTANDING FEEDBACK
# ---------------------------------
if st.session_state.last_answer:

    st.markdown("#### How well did you understand this?")

    c1, c2, c3 = st.columns(3)

    if c1.button("👍 Understood"):
        st.session_state.feedback_log.append("Understood")
        st.success("Great — keep going!")

    if c2.button("⚠️ Partial Understanding"):
        st.session_state.feedback_log.append("Partial")
        st.info("You may ask for a simpler explanation.")

    if c3.button("❌ Did Not Understand"):
        st.session_state.feedback_log.append("Not Understood")
        st.warning("You may request simpler explanation or more examples.")


# ---------------------------------
#  FOLLOW-UP SUPPORT
# ---------------------------------
st.markdown("#### Follow-up Support")

f1, f2 = st.columns(2)

if f1.button("🧩 Explain in Simpler Words"):
    generate_response("Explain again in simpler words", subject, depth, style, "simpler")

if f2.button("📌 Give More Real-World Examples"):
    generate_response("Give more real-world examples", subject, depth, style, "more_examples")


# ---------------------------------
#  DOWNLOAD SUMMARY
# ---------------------------------
st.divider()
st.subheader("📥 Download Learning Summary")

summary_text = generate_summary()

st.text_area("Summary Preview", summary_text, height=220)

if st.session_state.meta_log:
    st.download_button("Download as TXT", summary_text, file_name="learning_summary.txt")

    if st.button("Download as PDF"):
        file = export_pdf()
        st.success(f"Saved: {file}")
else:
    st.info("Ask at least one question to generate a summary.")
