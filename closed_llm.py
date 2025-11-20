# === Closed-source LLM helpers (optional) ===
import os
from openai import OpenAI
import anthropic  # lazy import
import google.generativeai as genai

def call_openai_chat(messages, model: str = "gpt-4o"):
    """
    Call OpenAI Chat Completion API.
    Requires OPENAI_API_KEY in environment.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Please set it in your environment.")
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    return resp.choices[0].message.content.strip()


def call_claude_chat(messages, model: str = "claude-3-5-sonnet-latest"):
    """
    Call Anthropic Claude Messages API.
    Requires ANTHROPIC_API_KEY in environment.
    """    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY. Please set it in your environment.")
    
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=messages,
    )
    # Claude는 content가 list로 옴
    return resp.content[0].text.strip()

def call_gemini_chat(messages, model="gemini-1.5-flash"):
    """
    Call Google Gemini chat-completion style API.
    Requires GEMINI_API_KEY in environment.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY. Please set it in your environment.")
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    combined_prompt = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        combined_prompt += f"{role.upper()}:\n{content}\n\n"

    response = genai.GenerativeModel(model).generate_content(combined_prompt)

    return response.text.strip()