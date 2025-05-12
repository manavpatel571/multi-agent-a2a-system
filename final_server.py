# final_server.py (simplified)
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import traceback
import requests
import json

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('final_server')

load_dotenv()
app = Flask(__name__)

# Get OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY not set in environment variables")
else:
    logger.info("OpenAI API key configured")

SYSTEM_PROMPT = (
    "You are an expert assistant. "
    "Use the provided context and search results to answer the user query comprehensively."
)

AGENT_CARD = {
    "name": "FinalAgent",
    "description": "Generates the final response using LLM.",
    "url": "http://localhost:5004",
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
        logger.info(f"Received request with ID: {data.get('id')}")
        
        # Extract parts from the message
        parts = data["message"]["parts"]
        prompt = "\n".join([part.get("text", "") for part in parts])
        logger.info(f"Constructed prompt: {prompt[:200]}...")
        
        # Check if OpenAI API key is set
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not configured")
            return jsonify({
                "id": data.get("id"),
                "status": {"state": "completed"},
                "messages": [
                    {"role": "agent", "parts": [{"text": "I apologize, but the language model service is not properly configured at the moment."}]}
                ]
            })
        
        # Use OpenAI API directly with requests
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }
            
            payload = {
                "model": "gpt-3.5-turbo",  # Use gpt-3.5-turbo as it's more widely available
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            logger.info("Calling OpenAI API for response generation")
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            reply = result["choices"][0]["message"]["content"].strip()
            logger.info(f"Generated reply: {reply[:100]}...")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    logger.error(f"OpenAI error details: {json.dumps(error_detail)}")
                except:
                    logger.error(f"OpenAI error response text: {e.response.text}")
            return jsonify({
                "id": data.get("id"),
                "status": {"state": "completed"},
                "messages": [
                    {"role": "agent", "parts": [{"text": "I apologize, but I'm having trouble generating a response right now. The language model service is experiencing issues."}]}
                ]
            })
        except Exception as e:
            logger.error(f"Other error in OpenAI call: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                "id": data.get("id"),
                "status": {"state": "completed"},
                "messages": [
                    {"role": "agent", "parts": [{"text": "I apologize, but I'm having trouble processing your request at the moment."}]}
                ]
            })
        
        # Return the response
        return jsonify({
            "id": data.get("id"),
            "status": {"state": "completed"},
            "messages": [
                {"role": "agent", "parts": [{"text": reply}]} 
            ]
        })
    
    except Exception as e:
        logger.error(f"Error in handle_task: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "id": data.get("id", "unknown") if "data" in locals() else "unknown",
            "status": {"state": "completed"},  # Always return completed, not error
            "messages": [
                {"role": "agent", "parts": [{"text": "I apologize, but there was an error processing your request. Please try again later."}]}
            ]
        })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5004, debug=True)

