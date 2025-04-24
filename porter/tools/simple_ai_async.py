# -*- coding: utf-8 -*-
import os
import asyncio
from openai import AsyncOpenAI, OpenAI
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file

# --- OpenAI Configuration ---
api_key = os.getenv("OPENAI_API_KEY")

# Support for custom base URLs (e.g., OpenRouter, local models)
openai_base_url = os.getenv("OPENAI_API_BASE_URL")

# Configure the clients
if openai_base_url:
    client = OpenAI(api_key=api_key, base_url=openai_base_url)
    async_client = AsyncOpenAI(api_key=api_key, base_url=openai_base_url)
else:
    client = OpenAI(api_key=api_key)
    async_client = AsyncOpenAI(api_key=api_key)

LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gpt-3.5-turbo")
print(f"Model: {LLM_MODEL_NAME}")

async def get_ai_response_async(prompt, max_tokens=1000, temperature=0.8):
    """Asynchronous version of get_ai_response"""
    if not api_key:
        return None

    print(f"Model: {LLM_MODEL_NAME}")
    try:
        response = await async_client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,  # Balance creativity and predictability
            n=1,
            stop=None,
        )

        text_content = response.choices[0].message.content or ""  # Ensure string
        text_content = text_content.strip()

        # Basic cleanup: LLMs sometimes wrap responses in quotes
        if len(text_content) > 1 and text_content.startswith('"') and text_content.endswith('"'):
            text_content = text_content[1:-1].strip()
        if len(text_content) > 1 and text_content.startswith("'") and text_content.endswith("'"):
            text_content = text_content[1:-1].strip()

        # Return None if empty AFTER stripping and cleanup
        if not text_content:
            return None
        else:
            return text_content

    except Exception as e:
        # Catch other unexpected errors (network issues, library errors)
        print(f"OpenAI API error: {e}")
        return None


def get_ai_response(prompt, max_tokens=1000, temperature=0.8):
    """Synchronous version of get_ai_response for backwards compatibility"""
    if not api_key:
        return None

    print(f"Model: {LLM_MODEL_NAME}")
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,  # Balance creativity and predictability
            n=1,
            stop=None,
        )

        text_content = response.choices[0].message.content or ""  # Ensure string
        text_content = text_content.strip()

        # Basic cleanup: LLMs sometimes wrap responses in quotes
        if len(text_content) > 1 and text_content.startswith('"') and text_content.endswith('"'):
            text_content = text_content[1:-1].strip()
        if len(text_content) > 1 and text_content.startswith("'") and text_content.endswith("'"):
            text_content = text_content[1:-1].strip()

        # Return None if empty AFTER stripping and cleanup
        if not text_content:
            return None
        else:
            return text_content

    except Exception as e:
        # Catch other unexpected errors (network issues, library errors)
        print(f"OpenAI API error: {e}")
        return None
