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
VALIDATION_MODEL: str = os.getenv("VALIDATION_MODEL", LLM_MODEL_NAME)
print(f"Model: {LLM_MODEL_NAME}, Validation model: {VALIDATION_MODEL}")

async def get_ai_response_async(prompt, model=LLM_MODEL_NAME, max_tokens=1000, temperature=0.8):
    """Asynchronous version of get_ai_response"""
    if not api_key:
        return None

    print(f"Model: {model}")
    try:
        response = await async_client.chat.completions.create(
            model=model,
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

async def get_validated_response_async(prompt, retries=3):
    while retries > 0:
        # Get the initial response from the LLM
        original_response = await get_ai_response_async(prompt)

        if not original_response:
            print("Failed to get a valid response.")
            return None

        # Construct the validation prompt
        validation_prompt = f"""
            Is this a valid response to this prompt?
            On a scale of 0 to 1, only consider it valid if it is above .9 rating.
            If it is valid, respond with the number 1.
            If not, respond with constructive feedback.
            ---
            Original prompt:
                '{prompt}',
            ---
            Proposed response:
                '{original_response}'
            ---
            Please evaluate and respond with 1 if the response is valid and direct feedback if not.
            """

        print(f"{validation_prompt=}")

        # Get feedback from the validation model
        validation_response = await get_ai_response_async(validation_prompt, model=VALIDATION_MODEL)

        print(f"{validation_response}")

        if not validation_response:
            print("Failed to validate response.")
            return None

        # Check if the validation is successful
        if validation_response == "1":
            return original_response
        else:
            prompt = f"Please rephrase your response to address feedback. Original Prompt: '{prompt}', Feedback: '{validation_response}'"

        retries -= 1
