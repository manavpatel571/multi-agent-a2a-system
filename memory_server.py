# memory_server.py (enhanced)
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import traceback
import requests
import uuid

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('memory_server')

load_dotenv()
app = Flask(__name__)

# Simple in-memory context store
user_context = {
    "preferences": {
        "travel": ["Paris", "London", "Tokyo"],
        "weather": "interested in weather forecasts",
        "food": "likes French cuisine",
        "ipl": "follows IPL cricket",
    }
}

SEARCH_AGENT_URL = os.getenv("SEARCH_URL", "http://localhost:5003/tasks/send")

AGENT_CARD = {
    "name": "MemoryAgent",
    "description": "Retrieves user context and preferences from memory.",
    "url": "http://localhost:5002",
    "version": "1.0",
    "capabilities": {"streaming": False, "pushNotifications": False}
}

def call_agent(url, text=None, parts=None, metadata=None):
    """Call another agent (HTTP POST) and return its response text."""
    try:
        payload = {
            "id": str(uuid.uuid4()),
            "message": {
                "role": "user",
                "parts": parts or ([{"text": text}] if text else [])
            }
        }
        if metadata:
            payload["metadata"] = metadata
        logger.info(f"Calling agent at {url} with payload: {str(payload)[:200]}...")
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        msgs = data.get("messages", [])
        if not msgs:
            return ""
        last_msg = msgs[-1]
        parts = last_msg.get("parts", [])
        result = "".join(p.get("text", "") for p in parts)
        return result
    except Exception as e:
        logger.error(f"Error calling agent at {url}: {str(e)}")
        return f"Error calling agent: {str(e)}"

@app.get("/.well-known/agent.json")
def agent_card():
    return jsonify(AGENT_CARD)

@app.post("/tasks/send")
def handle_task():
    try:
        data = request.get_json()
        user_text = data.get("message", {}).get("parts", [{}])[0].get("text", "")
        metadata = data.get("metadata", {})
        logger.info(f"Received query for context: {user_text}")
        logger.info(f"Received metadata: {metadata}")

        # If the query starts with 'search:', call the search agent directly
        search_result = None
        if user_text.strip().lower().startswith("search:"):
            search_query = user_text[len("search:"):].strip()
            logger.info(f"Triggering direct search agent call for: {search_query}")
            search_result = call_agent(SEARCH_AGENT_URL, text=search_query, metadata={**metadata, "called_by": "MemoryAgent"})

        # Simple keyword matching to return relevant context
        context_parts = []

        # Check for travel-related keywords
        if any(city.lower() in user_text.lower() for city in user_context["preferences"]["travel"]):
            context_parts.append("User is interested in travel destinations.")
            # Add specific city context
            for city in user_context["preferences"]["travel"]:
                if city.lower() in user_text.lower():
                    context_parts.append(f"User has previously asked about {city}.")

        # Check for weather-related keywords
        if "weather" in user_text.lower():
            context_parts.append(user_context["preferences"]["weather"])

        # Check for food-related keywords
        if "food" in user_text.lower() or "eat" in user_text.lower() or "restaurant" in user_text.lower():
            context_parts.append(user_context["preferences"]["food"])

        # If search_result was retrieved, append it to context
        if search_result:
            context_parts.append(f"[SearchAgent result]: {search_result}")

        # Combine context
        context = " ".join(context_parts)
        logger.info(f"Retrieved context: {context}")

        response = {
            "id": data.get("id"),
            "status": {"state": "completed"},
            "messages": [
                {"role": "agent", "parts": [{"text": context}]}
            ]
        }
        # Propagate metadata if present
        if metadata:
            response["metadata"] = metadata
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in handle_task: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "id": data.get("id", "unknown") if "data" in locals() else "unknown",
            "status": {"state": "error", "message": str(e)},
            "messages": [
                {"role": "agent", "parts": [{"text": ""}]}  # Return empty context on error
            ]
        }), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=True)