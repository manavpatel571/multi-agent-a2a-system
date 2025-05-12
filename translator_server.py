# translator_server.py 
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import traceback
import requests
import json

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('translator_server')

load_dotenv()
app = Flask(__name__)

# Get OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY not set in environment variables")
else:
    logger.info("OpenAI API key configured")

AGENT_CARD = {
    "name": "TranslatorAgent",
    "description": "Translates non-English queries into English",
    "url": "http://localhost:5001",
    "version": "1.0",
    "capabilities": {"streaming": False, "pushNotifications": False}
}

@app.get("/.well-known/agent.json")
def agent_card():
    return jsonify(AGENT_CARD)

@app.post("/tasks/send")
def handle_task():
    try:
        data = request.get_json()
        task_id = data.get("id", "unknown")
        user_text = data["message"]["parts"][0]["text"]
        logger.info(f"Received text to translate: {user_text}")
        
        # Check if OpenAI API key is set
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not configured")
            return jsonify({
                "id": task_id,
                "status": {"state": "completed"},
                "messages": [
                    {"role": "agent", "parts": [{"text": user_text}]}  # Return original text if no API key
                ]
            })
        
        # Use OpenAI API directly
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }
            
            payload = {
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "Translate the user text into English."},
                    {"role": "user", "content": user_text}
                ],
                "temperature": 0.3
            }
            
            logger.info("Calling OpenAI API for translation")
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            response.raise_for_status()
            result = response.json()
            translation = result["choices"][0]["message"]["content"].strip()
            logger.info(f"Translated text: {translation}")
            
        except Exception as e:
            logger.error(f"Error translating text: {str(e)}")
            logger.error(traceback.format_exc())
            translation = user_text  # Fall back to original text
        
        return jsonify({
            "id": task_id,
            "status": {"state": "completed"},
            "messages": [
                {"role": "agent", "parts": [{"text": translation}]}
            ]
        })
    
    except Exception as e:
        logger.error(f"Error in handle_task: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "id": data.get("id", "unknown") if "data" in locals() else "unknown",
            "status": {"state": "error", "message": str(e)},
            "messages": [
                {"role": "agent", "parts": [{"text": data["message"]["parts"][0]["text"] if "data" in locals() else "Error processing request"}]}
            ]
        }), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)