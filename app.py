import os
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-here-change-in-production")
CORS(app)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Verification code
VERIFICATION_CODE = "1234567890"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def generate_response(prompt):
    """Generate a response from the OpenAI Assistant API."""
    assistant_id = os.environ.get("ASSISTANT_ID")
    if not assistant_id:
        return "ASSISTANT_ID environment variable not set. Please check your .env file."

    if not os.environ.get("OPENAI_API_KEY"):
        return "OPENAI_API_KEY environment variable not set. Please check your .env file."

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
            if run.status == 'failed':
                return f"Assistant run failed: {run.last_error}"

        messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )
        response_text = messages.data[0].content[0].text.value
        # Prepend Chopper signature to response
        return f"[Chopper]: {response_text}"
    except Exception as e:
        return f"An error occurred: {str(e)}"

@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login')
def login():
    if session.get('authenticated'):
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/verify', methods=['POST'])
def verify():
    code = request.form.get('code', '')
    if code == VERIFICATION_CODE:
        session['authenticated'] = True
        return redirect(url_for('index'))
    else:
        return redirect(url_for('login') + '?error=1')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/about')
@login_required
def about():
    return render_template('about.html')

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    response = generate_response(user_message)
    return jsonify({'response': response})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)