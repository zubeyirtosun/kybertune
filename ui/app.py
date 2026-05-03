import streamlit as st
import requests
import os
import time

st.set_page_config(page_title="KyberTune Chat UI", page_icon="🤖", layout="centered")

# --- Custom Premium Styling ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #08090a; color: #e1e1e1; }
    
    /* Status Badge Styling */
    .status-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(255, 255, 255, 0.03);
        padding: 12px 20px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 30px;
    }
    .badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-online { background: rgba(16, 185, 129, 0.1); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.2); }
    .badge-loading { background: rgba(245, 158, 11, 0.1); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.2); }
    .badge-offline { background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.2); }
    
    /* Input Styling */
    .stChatInputContainer { background-color: transparent !important; }
    .stChatInput { border-radius: 10px !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; }
    </style>
""", unsafe_allow_html=True)

# Configuration
SERVING_URL = os.getenv("SERVING_URL", "http://localhost:8000/generate")
HEALTH_URL = SERVING_URL.replace("/generate", "/health")

def check_model_health():
    try:
        response = requests.get(HEALTH_URL, timeout=1.0)
        if response.status_code == 200:
            return "READY", response.json()
        return "LOADING", None
    except:
        return "OFFLINE", None

# --- UI Header ---
st.title("KyberTune")
st.caption("LLMOps Pipeline • Phi-3-mini • GPU Accelerated")

# Status Display
status, info = check_model_health()

status_html = ""
if status == "READY":
    status_html = f'<div class="status-container"><span>System Status</span><span class="badge badge-online">🟢 Online • {info.get("adapter", "Base")}</span></div>'
elif status == "LOADING":
    status_html = '<div class="status-container"><span>System Status</span><span class="badge badge-loading">🟡 Model Loading...</span></div>'
    time.sleep(4)
    st.rerun()
else:
    status_html = '<div class="status-container"><span>System Status</span><span class="badge badge-offline">🔴 Offline</span></div>'

st.markdown(status_html, unsafe_allow_html=True)

# --- Chat Interface ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

input_msg = "Send a message..." if status == "READY" else "Waiting for model to wake up..."
if prompt := st.chat_input(input_msg, disabled=(status != "READY")):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        msg_placeholder = st.empty()
        msg_placeholder.markdown("*(Thinking...)*")
        
        try:
            response = requests.post(SERVING_URL, json={"prompt": prompt, "max_length": 128}, timeout=180)
            if response.status_code == 200:
                answer = response.json()["response"]
                msg_placeholder.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            else:
                msg_placeholder.error(f"Error: {response.text}")
        except Exception as e:
            msg_placeholder.error(f"Service unreachable: {e}")

# Sidebar for controls only
with st.sidebar:
    st.header("Controls")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.markdown(f"**Endpoint:**\n`{SERVING_URL}`")
