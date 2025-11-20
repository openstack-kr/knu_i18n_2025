# === Closed-source LLM helpers (optional) ===
import os
from openai import OpenAI
import anthropic  # lazy import
import google.generativeai as genai

def call_openai_chat(messages, model: str = "gpt-4o"):
    """
    Call the OpenAI Chat Completions API.

    This function sends a list of chat messages to an OpenAI model
    and returns the model's textual response. It requires an
    `OPENAI_API_KEY` environment variable to be set.

    Args:
        messages (list[dict]): A list of chat messages, each containing
            "role" and "content" fields (e.g., {"role": "user", "content": "..."}).
        model (str): The OpenAI model name to use. Defaults to "gpt-4o".

    Returns:
        str: The model's generated message content.

    Raises:
        RuntimeError: If `OPENAI_API_KEY` is not set in the environment.
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
    Call the Anthropic Claude Messages API.

    This function sends a chat-style message list to a Claude model
    and returns the generated text output. The API requires an
    `ANTHROPIC_API_KEY` environment variable.

    Note:
        Claude returns the message content as a list of text blocks.
        This helper currently extracts and returns only the first block.

    Args:
        messages (list[dict]): A list of chat messages with "role" and "content".
        model (str): Name of the Claude model to call. Defaults to
            "claude-3-5-sonnet-latest".

    Returns:
        str: The model's generated text.

    Raises:
        RuntimeError: If `ANTHROPIC_API_KEY` is missing.
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
    Call the Google Gemini API using a chat-style message sequence.

    Gemini's API does not use the same role-based structure as OpenAI/Anthropic,
    so this function flattens all messages into a single combined text prompt.
    The `GEMINI_API_KEY` environment variable must be set.

    Args:
        messages (list[dict]): A list of chat messages. Each entry should contain
            "role" (e.g., "user" or "system") and "content" (the text).
        model (str): Gemini model name to use. Defaults to "gemini-1.5-flash".

    Returns:
        str: The generated response text from Gemini.

    Raises:
        RuntimeError: If `GEMINI_API_KEY` is not set.
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