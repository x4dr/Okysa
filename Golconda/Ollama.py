from functools import lru_cache

import aiohttp
import discord
import requests

from Golconda.Storage import evilsingleton

SYSTEM_PROMPT = (
    "You are a capricous goddess in a fantasy world. A dark goddess of twists and complicated plans, "
    "haughty, but not overly dramatic, never introduces herself or states her name, which is Okysa, "
    "as people know who they are talking to. "
    "Stay formal aloof and mysterious."
    "Never generate roleplay like you are doing an action or any asterisk/paranthesis roleplay. "
    "As a god you do not act in the material world, as that is beneath you, "
    "even if you are all powerful and all knowing. "
    "Provide interesting banter and entertain Users as this character. "
    "Messages should stay rather short, as you are chatting, not writing long rp. "
    "Never generate messages from anyone but Okysa. Do not predict user input. Do not Prefix your messages. "
    "You must not state your name. Do not introduce yourself in any way."
    "Messages not be adressed to your directly, this is a general chatroom, decide from context."
    "Keep your response concise and under 3 sentences."
)
MODEL_NAME = "impish-mind"
# Per-user chat history
user_logs = {}


@lru_cache
def get_context_length():
    response = requests.post(
        f"{ evilsingleton().ollama }/api/show", json={"model": MODEL_NAME}
    )
    j = response.json()
    return j.get("context_length", 4096)  # Default if not found


# Trim chat history if it exceeds context length
def trim_history(history, context_limit):
    total_length = sum(len(msg) for msg in history)
    while total_length > context_limit and history:
        history.pop(0)  # Remove oldest messages
        total_length = sum(len(msg) for msg in history)
    return history


def is_ollama_up():
    try:
        response = requests.get(f"{evilsingleton().ollama}/api/tags", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


async def get_ollama_response(message: discord.Message):
    user_id = message.author.id

    if user_id not in user_logs:
        user_logs[user_id] = []

    # Append user message
    user_logs[user_id].append({"role": "user", "content": message.content})
    if is_ollama_up():
        user_logs[user_id] = trim_history(user_logs[user_id], get_context_length())

        # Format messages correctly
        formatted_messages = ""
        for msg in user_logs[user_id]:
            formatted_messages += (
                f"<|start_header_id|>{msg['role']}<|end_header_id|>\n\n{message.author.display_name}: "
                f"{msg['content']}<|eot_id|>\n"
            )

        # Append system prompt and assistant start
        full_prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n{SYSTEM_PROMPT}<|eot_id|>\n"
            + formatted_messages
        )
        full_prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"
        async with message.channel.typing():
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{evilsingleton().ollama}/api/generate",
                    json={"model": MODEL_NAME, "prompt": full_prompt, "stream": False},
                ) as response:
                    data = await response.json()
                    ai_response = data.get("response", "")

            # Append AI response to chat history
            user_logs[user_id].append({"role": "assistant", "content": ai_response})

            await message.reply(ai_response)
            print(ai_response)
    else:
        await message.add_reaction("💤")
