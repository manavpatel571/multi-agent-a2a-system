# router_server.py

from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import uuid
import json
import requests
import traceback
from langdetect import detect, LangDetectException

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('router')

load_dotenv()
app = Flask(__name__)

# Agent endpoints
TRANSLATOR_URL = os.getenv("TRANSLATOR_URL", "http://localhost:5001/tasks/send")
MEMORY_URL     = os.getenv("MEMORY_URL",     "http://localhost:5002/tasks/send")
SEARCH_URL     = os.getenv("SEARCH_URL",     "http://localhost:5003/tasks/send")
FINAL_URL      = os.getenv("FINAL_URL",      "http://localhost:5004/tasks/send")

# Log configured endpoints
logger.info(f"Translator URL: {TRANSLATOR_URL}")
logger.info(f"Memory URL: {MEMORY_URL}")
logger.info(f"Search URL: {SEARCH_URL}")
logger.info(f"Final URL: {FINAL_URL}")

AGENT_CARD = {
    "name": "RouterAgent",
    "description": "Orchestrates language detection, translation, memory, search, and final response.",
    "url": "http://localhost:5006",
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
        task_id = data.get("id", str(uuid.uuid4()))
        
        # Validate input
        if not data or "message" not in data or "parts" not in data["message"]:
            logger.error(f"Invalid request format: {data}")
            return jsonify({
                "id": task_id,
                "status": {"state": "error", "message": "Invalid request format"},
                "messages": [
                    {"role": "agent", "parts": [{"text": "Error: Invalid request format"}]}
                ]
            }), 400
            
        user_text = data["message"]["parts"][0].get("text", "")
        logger.info(f"Processing query: '{user_text}'")
        
        # 1️⃣ Language Detection & Translation
        detected_lang = "en"  # Default to English
        try:
            detected_lang = detect(user_text)
            logger.info(f"Detected language: {detected_lang}")
            
            if detected_lang != 'en':
                logger.info("Non-English query detected, translating...")
                translated_text = call_agent(TRANSLATOR_URL, text=user_text)
                # Only update if we got something back
                if translated_text and not translated_text.startswith("Error"):
                    logger.info(f"Translated text: '{translated_text}'")
                    user_text = translated_text
                else:
                    logger.warning(f"Translation failed: {translated_text}, using original text")
        except LangDetectException as e:
            logger.warning(f"Language detection failed: {e}, assuming English")
    
        # 2️⃣ Memory Context Retrieval
        logger.info("Retrieving context from memory...")
        context = call_agent(MEMORY_URL, text=user_text)
        if context and not context.startswith("Error"):
            logger.info(f"Retrieved context: '{context[:100]}...'")
        else:
            logger.warning(f"Memory retrieval issue: {context}")
            context = ""  # Reset to empty if there was an error
    
        # 3️⃣ Real-time Search Fetch
        logger.info("Fetching search results...")
        search_res = call_agent(SEARCH_URL, text=user_text)
        if search_res and not search_res.startswith("Error"):
            logger.info(f"Search results: '{search_res[:100]}...'")
        else:
            logger.warning(f"Search retrieval issue: {search_res}")
            search_res = ""  # Reset to empty if there was an error
    
        # 4️⃣ Final Response Generation
        logger.info("Generating final response...")
        # Create combined parts - make sure none are None
        combined_parts = [
            {"text": f"User query: {user_text}"},
        ]
        if context:
            combined_parts.append({"text": f"Context: {context}"})
        if search_res:
            combined_parts.append({"text": f"Search results: {search_res}"})
        
        final_reply = call_agent(FINAL_URL, parts=combined_parts)
        if final_reply and not final_reply.startswith("Error"):
            logger.info(f"Final response: '{final_reply[:100]}...'")
        else:
            logger.error(f"Final response generation failed: {final_reply}")
            final_reply = "I apologize, but I'm having trouble processing your request at the moment. Please try again later."
    
        # Assemble A2A response
        response = {
            "id": task_id,
            "status": {"state": "completed"},
            "messages": [
                data["message"],
                {"role": "agent", "parts": [{"text": final_reply}]}        
            ]
        }
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in handle_task: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "id": data.get("id", str(uuid.uuid4())) if "data" in locals() else str(uuid.uuid4()),
            "status": {"state": "error", "message": str(e)},
            "messages": [
                {"role": "agent", "parts": [{"text": f"An error occurred: {str(e)}"}]}
            ]
        }), 500


def call_agent(url, text=None, parts=None):
    """Call an agent service and handle errors gracefully."""
    try:
        payload = {
            "id": str(uuid.uuid4()),
            "message": {
                "role": "user",
                "parts": parts or [{"text": text}]
            }
        }
        logger.info(f"Calling {url}")
        logger.debug(f"Payload: {json.dumps(payload)[:200]}...")
        
        # Set a reasonable timeout
        resp = requests.post(url, json=payload, timeout=30)
        
        # Log response information
        logger.info(f"Response from {url}: Status {resp.status_code}")
        
        # Try to get JSON response
        try:
            data = resp.json()
            logger.debug(f"Response data: {json.dumps(data)[:200]}...")
        except Exception as e:
            logger.error(f"Failed to parse JSON from {url}: {e}")
            logger.error(f"Raw response: {resp.text[:200]}...")
            return f"Error: Invalid response from {url.split('/')[-2]}"
        
        # Handle non-200 responses without raising exceptions
        if resp.status_code != 200:
            logger.warning(f"Non-200 status from {url}: {resp.status_code}")
            return f"Error from {url.split('/')[-2]}: {resp.status_code}"
        
        # Extract text from messages
        msgs = data.get("messages", [])
        if not msgs:
            logger.warning(f"No messages in response from {url}")
            return ""
        
        last_msg = msgs[-1]
        parts = last_msg.get("parts", [])
        result = "".join(p.get("text", "") for p in parts)
        return result
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error calling {url}: {str(e)}")
        return f"Error connecting to {url.split('/')[-2]}: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error calling {url}: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error communicating with {url.split('/')[-2]}: {str(e)}"

if __name__ == "__main__":
    # bind only to localhost, enable debug to see stack-traces
    app.run(host="127.0.0.1", port=5006, debug=True)
