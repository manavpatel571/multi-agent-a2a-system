# enhanced_test_client.py
import requests
import json
import sys
import uuid

def test_with_details(query):
    """
    Test the agent system showing the detailed outputs from each component.
    """
    print(f"\n{'='*80}")
    print(f"PROCESSING QUERY: '{query}'")
    print(f"{'='*80}")
    
    # 1. First, directly test language detection and possible translation
    try:
        from langdetect import detect
        detected_lang = detect(query)
        print(f"\n📝 LANGUAGE DETECTION: Detected '{detected_lang}'")
        
        if detected_lang != 'en':
            print(f"\n🔤 TRANSLATOR AGENT:")
            print(f"{'─'*50}")
            translated = call_agent("http://localhost:5001/tasks/send", query)
            print(f"Original: '{query}'")
            print(f"Translated: '{translated}'")
            # Update query for downstream agents
            query = translated
    except Exception as e:
        print(f"Language detection error: {e}")
    
    # 2. Query Memory Agent
    print(f"\n🧠 MEMORY AGENT:")
    print(f"{'─'*50}")
    memory_context = call_agent("http://localhost:5002/tasks/send", query)
    print(f"Retrieved Context: '{memory_context or 'No relevant context found'}'")
    
    # 3. Query Search Agent
    print(f"\n🔍 SEARCH AGENT:")
    print(f"{'─'*50}")
    search_results = call_agent("http://localhost:5003/tasks/send", query)
    print(f"Search Results: '{search_results[:200]}...' (truncated)")
    
    # 4. Send combined info to Final Agent
    print(f"\n🤖 FINAL AGENT:")
    print(f"{'─'*50}")
    
    # Prepare combined parts similar to how the router does it
    combined_parts = [
        {"text": f"User query: {query}"},
    ]
    if memory_context:
        combined_parts.append({"text": f"Context: {memory_context}"})
    if search_results:
        combined_parts.append({"text": f"Search results: {search_results}"})
    
    payload = {
        "id": str(uuid.uuid4()),
        "message": {
            "role": "user",
            "parts": combined_parts
        }
    }
    
    # Call final agent directly with the combined information
    final_response = call_with_payload("http://localhost:5004/tasks/send", payload)
    print(f"Final Response: '{final_response}'")
    
    # 5. Now call the router for comparison
    print(f"\n🔄 FULL ROUTER FLOW:")
    print(f"{'─'*50}")
    router_response = call_agent("http://localhost:5006/tasks/send", query)
    print(f"Router Response: '{router_response}'")
    
    print(f"\n{'='*80}")
    print(f"END OF PROCESSING")
    print(f"{'='*80}")

def call_agent(url, text):
    """Call an agent with a text query."""
    payload = {
        "id": str(uuid.uuid4()),
        "message": {
            "role": "user",
            "parts": [{"text": text}]
        }
    }
    return call_with_payload(url, payload)

def call_with_payload(url, payload):
    """Call an agent with a prepared payload."""
    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        msgs = data.get("messages", [])
        if not msgs:
            return "No valid response received"
        
        # Get the agent's response message (last message)
        last_msg = msgs[-1]
        parts = last_msg.get("parts", [])
        result = "".join(p.get("text", "") for p in parts)
        return result
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Get query from command line argument or use a default
    query = sys.argv[1] if len(sys.argv) > 1 else "What is the weather in Paris?"
    test_with_details(query)