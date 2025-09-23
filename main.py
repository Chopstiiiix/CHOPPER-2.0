import os
import sys
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize the OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def generate_response(prompt):
    """Generate a response from the OpenAI Assistant API."""
    assistant_id = os.environ.get("ASSISTANT_ID")
    if not assistant_id:
        return "ASSISTANT_ID environment variable not set."

    try:
        thread = client.beta.threads.create()
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id
        )

        while run.status != 'completed':
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

        messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )
        return messages.data[0].content[0].text.value
    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_prompt = ' '.join(sys.argv[1:])
        ai_response = generate_response(user_prompt)
        print(f"AI: {ai_response}")
    else:
        print("Usage: python main.py <your-prompt>")
