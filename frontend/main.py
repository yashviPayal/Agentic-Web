import streamlit as st
import requests
import os
import threading
import time
from dotenv import load_dotenv

load_dotenv()

# Config
API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Thread safety classes
class ThreadResult:
    def __init__(self):
        self.result = None
        self.error = None
        self.done = False

def run_chat_in_thread_safe(api_url, api_messages, container):
    try:
        response = requests.post(
            f"{api_url}/chat",
            json={"messages": api_messages},
            timeout=600  # Browsing can easily take 3-5+ minutes
        )
        if response.status_code == 200:
            container.result = response.json()
        else:
            container.error = f"Backend error: {response.text}"
    except Exception as e:
        container.error = str(e)
    finally:
        container.done = True

# Page setup
st.set_page_config(
    page_title="Agentic Web AI",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "api_messages" not in st.session_state:
    st.session_state.api_messages = []

if "agent_running" not in st.session_state:
    st.session_state.agent_running = False

if "chat_result" not in st.session_state:
    st.session_state.chat_result = None

if "chat_error" not in st.session_state:
    st.session_state.chat_error = None

if "waiting_for_input" not in st.session_state:
    st.session_state.waiting_for_input = False

if "prompt" not in st.session_state:
    st.session_state.prompt = None

# Sidebar
with st.sidebar:
    st.title("🌐 Agentic Web AI")
    st.markdown("---")
    
    st.subheader("💡 Example Prompts")
    st.markdown("""
    - *"Get me the content from https://example.com"*
    - *"What does the Hacker News front page say?"*
    - *"Browse https://news.ycombinator.com and summarize the top stories"*
    - *"Extract the main article from https://blog.example.com/post"*
    """)
    
    st.markdown("---")
    st.info("Powered by OpenRouter + Playwright + FastAPI")

# Main chat interface
st.title("💬 Chat with Web AI Agent")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("tool_used"):
            st.markdown(f"🔧 **Tool Used:** `{msg['tool_used']}`")
        
        st.markdown(msg["content"])
        
        if msg["role"] == "assistant" and msg.get("raw_url"):
            st.markdown(f"🔗 **Source:** [{msg['raw_url']}]({msg['raw_url']})")

# Polling and background thread execution checks
if st.session_state.agent_running:
    container = st.session_state.get("thread_container")
    if container and container.done:
        st.session_state.agent_running = False
        st.session_state.waiting_for_input = False
        st.session_state.prompt = None
        
        if container.error:
            st.error(container.error)
        elif container.result:
            result = container.result
            
            # Add AI response to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["response"],
                "tool_used": result.get("tool_used"),
                "raw_url": result.get("raw_url"),
                "tool_result": result.get("tool_result")
            })
            
            # Update api messages with returned new_messages
            if "new_messages" in result and result["new_messages"]:
                st.session_state.api_messages.extend(result["new_messages"])
            else:
                st.session_state.api_messages.append({
                    "role": "assistant",
                    "content": result["response"]
                })
                
            # If tool was used, show raw data in expander (only for the last response)
            if result.get("tool_result") and result["tool_result"].get("success"):
                with st.expander("📄 Raw Scraped Data", expanded=True):
                    tool_res = result["tool_result"]
                    st.markdown(f"**Title:** {tool_res.get('title', 'N/A')}")
                    st.markdown(f"**URL:** {tool_res.get('url', 'N/A')}")
                    
                    if tool_res.get("links"):
                        st.subheader("🔗 Links Found")
                        for link in tool_res["links"][:10]:
                            st.markdown(f"- [{link.get('text', 'Link')}]({link.get('url')})")
                    
                    if tool_res.get("content"):
                        st.subheader("📝 Raw Content")
                        st.text_area("Content", tool_res["content"], height=300)
                        
        st.session_state.thread_container = None
        st.rerun()
    else:
        # Agent is still running
        if st.session_state.waiting_for_input:
            st.warning(f"⚠️ **Human Input/Action Required:** {st.session_state.prompt}")
            with st.form(key="human_input_form", clear_on_submit=True):
                human_ans = st.text_input("Response / Confirmation text", placeholder="Type response here (or leave blank and confirm if completed in browser)...")
                submitted_human = st.form_submit_button("Confirm & Resume AI")
                if submitted_human:
                    ans = human_ans.strip() if human_ans.strip() else "done"
                    try:
                        resp = requests.post(f"{API_URL}/human/response", json={"answer": ans})
                        if resp.status_code == 200:
                            st.session_state.waiting_for_input = False
                            st.session_state.prompt = None
                            st.success("Submitted! Resuming agent loop...")
                            st.rerun()
                        else:
                            st.error(f"Failed to submit: {resp.text}")
                    except Exception as e:
                        st.error(f"Error submitting response: {e}")
        else:
            with st.spinner("🤖 AI is thinking... (may browse the web)"):
                try:
                    status_resp = requests.get(f"{API_URL}/human/status")
                    if status_resp.status_code == 200:
                        status = status_resp.json()
                        if status.get("waiting"):
                            st.session_state.waiting_for_input = True
                            st.session_state.prompt = status["prompt"]
                            st.rerun()
                except Exception:
                    pass
                time.sleep(1.5)
                st.rerun()

# Input area
st.markdown("---")
if not st.session_state.agent_running:
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_area(
            "Your message",
            placeholder="Ask me to browse a website...",
            height=80
        )
        cols = st.columns([6, 1])
        with cols[0]:
            submitted = st.form_submit_button("🚀 Send", use_container_width=True)
        with cols[1]:
            clear_btn = st.form_submit_button("🗑️ Clear", use_container_width=True)
            
    if clear_btn:
        st.session_state.messages = []
        st.session_state.api_messages = []
        st.rerun()

    if submitted and user_input.strip():
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        st.session_state.api_messages.append({
            "role": "user",
            "content": user_input
        })
        
        st.session_state.agent_running = True
        st.session_state.chat_result = None
        st.session_state.chat_error = None
        st.session_state.waiting_for_input = False
        st.session_state.prompt = None
        
        # Start thread
        container = ThreadResult()
        st.session_state.thread_container = container
        thread = threading.Thread(
            target=run_chat_in_thread_safe,
            args=(API_URL, st.session_state.api_messages, container)
        )
        thread.start()
        st.rerun()
else:
    st.info("Agent is currently executing a task. Please wait or respond to the handoff request above.")

# Footer
st.markdown("---")
st.caption("Built with ❤️ using FastAPI + Playwright + Streamlit + OpenRouter")