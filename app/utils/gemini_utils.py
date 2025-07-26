import os

import google.generativeai as genai

model = genai.GenerativeModel("gemini-1.5-flash")


def get_gemini_response(messages: list[dict]) -> str:
    chat = model.start_chat(history=messages)
    response = chat.send_message(messages[-1]["parts"][0])
    return response.text
