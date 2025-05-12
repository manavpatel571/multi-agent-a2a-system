# test_all_detailed.py (with full response display)
import requests
import json
import sys
import uuid
import time
import datetime

def call_agent_with_details(name, url, payload):
    """Call an agent with detailed debugging information."""
    print(f"\n{'─'*20} {name.upper()} AGENT {'─'*20}")
    
    print(f"→ Sending to: {url}")
    print(f"→ Payload ID: {payload.get('id')}")
    
    try:
        start_time = time.time()
        resp = requests.post(url, json=payload, timeout=30)
        duration = time.time() - start_time
        print(f"→ Response time: {duration:.2f} seconds")
        print(f"→ Status code: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"→ Error response: {resp.text[:200]}...")
            return f"Error: HTTP {resp.status_code}", None
        
        # Try to parse the response
        try:
            data = resp.json()
            print(f"→ Response keys: {list(data.keys())}")
            
            # Store the full response for inspection
            full_response = data
            
            # Extract the text from the response
            if "messages" not in data:
                print(f"→ Missing 'messages' key. Response: {json.dumps(data)[:200]}...")
                return "Error: Invalid response (no messages)", full_response
            
            messages = data["messages"]
            print(f"→ Found {len(messages)} messages")
            
            # Get the last message (agent's response)
            if len(messages) < 1:
                print(f"→ No messages in response")
                return "Error: Empty messages list", full_response
                
            last_message = messages[-1]
            print(f"→ Last message role: {last_message.get('role')}")
            
            if "parts" not in last_message:
                print(f"→ No 'parts' in last message: {json.dumps(last_message)[:100]}...")
                return "Error: Invalid message format (no parts)", full_response
            
            parts = last_message["parts"]
            print(f"→ Found {len(parts)} parts in last message")
            
            if not parts:
                return "Error: Empty parts list", full_response
            
            # Extract text from all parts
            text_parts = []
            for part in parts:
                if "text" in part:
                    text_parts.append(part["text"])
            
            result = "".join(text_parts)
            print(f"→ Extracted text ({len(result)} chars)")
            print(f"→ TEXT START")
            print(result)  # Print the full text without truncation
            print(f"→ TEXT END")
            
            return result, full_response
            
        except json.JSONDecodeError:
            print(f"→ Non-JSON response: {resp.text[:200]}...")
            return "Error: Non-JSON response", None
            
    except requests.exceptions.Timeout:
        print(f"→ Timeout error: Request to {url} timed out after 30 seconds")
        return f"Error: Request timeout", None
    except requests.exceptions.ConnectionError:
        print(f"→ Connection error: Could not connect to {url}")
        return f"Error: Connection failed", None
    except Exception as e:
        print(f"→ Exception: {str(e)}")
        return f"Error: {str(e)}", None

def test_all_agents(query):
    """
    Test all agents in the system with detailed outputs, including direct memory→search chaining for 'search:' prefix queries.
    Always define translated_query, fallback if language detection fails.
    """
    """Test all agents in the system with detailed outputs."""
    session_id = str(uuid.uuid4())
    start_time = time.time()
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"\n{'='*80}")
    print(f"TESTING ALL AGENTS WITH QUERY: '{query}'")
    print(f"Session ID: {session_id}")
    print(f"Date/Time: {current_date}")
    print(f"{'='*80}")
    
    # Store results from each agent
    results = {}
    
    # 0. Special test: direct inter-agent chain via 'search:' prefix
    if query.strip().lower().startswith("search:"):
        print("\n🧪 TESTING MEMORY AGENT'S DIRECT SEARCH CHAIN")
        memory_payload = {
            "id": f"{session_id}-memory-chain",
            "message": {
                "role": "user",
                "parts": [{"text": query}]
            }
        }
        memory_context, memory_response = call_agent_with_details(
            "Memory (chain test)",
            "http://localhost:5002/tasks/send",
            memory_payload
        )
        print(f"\n[Chain Test] Memory agent response:\n{memory_context}")
        if "[SearchAgent result]:" in (memory_context or ""):
            print("✅ Memory agent included SearchAgent result in its context!")
        else:
            print("❌ Memory agent did NOT include SearchAgent result. Check implementation.")
        # Continue with normal test flow after this
    
    # 1. Language detection
    translated_query = query  # Always define, fallback to original query
    try:
        from langdetect import detect
        detected_lang = detect(query)
        print(f"\n📝 LANGUAGE DETECTION: Detected '{detected_lang}'")
        results['language'] = detected_lang
        
        # 2. Translator (if needed)
        if detected_lang != 'en':
            print("\n🔤 TESTING TRANSLATOR")
            translator_payload = {
                "id": f"{session_id}-translator",
                "message": {
                    "role": "user",
                    "parts": [{"text": query}]
                }
            }
            translated_text, translator_response = call_agent_with_details(
                "Translator", 
                "http://localhost:5001/tasks/send", 
                translator_payload
            )
            
            results['translator'] = {
                "result": translated_text,
                "full_response": translator_response
            }
            
            if not translated_text.startswith("Error:"):
                print(f"✅ Translation successful")
                translated_query = translated_text
            else:
                print(f"❌ Translation failed: {translated_text}")
    except Exception as e:
        print(f"❌ Language detection error: {e}")
        results['language_error'] = str(e)
        translated_query = query  # fallback
        print("⚠️ Using original query as translated_query.")
    
    # 3. Memory Agent
    print("\n🧠 TESTING MEMORY AGENT")
    memory_payload = {
        "id": f"{session_id}-memory",
        "message": {
            "role": "user",
            "parts": [{"text": translated_query}]
        }
    }
    memory_context, memory_response = call_agent_with_details(
        "Memory", 
        "http://localhost:5002/tasks/send", 
        memory_payload
    )
    
    results['memory'] = {
        "result": memory_context,
        "full_response": memory_response
    }
    
    # 4. Search Agent
    print("\n🔍 TESTING SEARCH AGENT")
    search_payload = {
        "id": f"{session_id}-search",
        "message": {
            "role": "user",
            "parts": [{"text": translated_query}]
        }
    }
    search_results, search_response = call_agent_with_details(
        "Search", 
        "http://localhost:5003/tasks/send", 
        search_payload
    )
    
    results['search'] = {
        "result": search_results,
        "full_response": search_response
    }
    
    # 5. Final Agent with combined information
    print("\n🤖 TESTING FINAL AGENT")
    
    # Prepare combined parts
    combined_parts = [
        {"text": f"User query: {translated_query}"}
    ]
    
    if memory_context and not memory_context.startswith("Error:"):
        combined_parts.append({"text": f"Context: {memory_context}"})
    
    if search_results and not search_results.startswith("Error:"):
        combined_parts.append({"text": f"Search results: {search_results}"})
    
    # Add current date information
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    combined_parts.append({"text": f"Current date: {current_date}. Please provide up-to-date information."})
    
    final_payload = {
        "id": f"{session_id}-final",
        "message": {
            "role": "user",
            "parts": combined_parts
        }
    }
    
    final_response_text, final_response_full = call_agent_with_details(
        "Final", 
        "http://localhost:5004/tasks/send", 
        final_payload
    )
    
    results['final'] = {
        "result": final_response_text,
        "full_response": final_response_full
    }
    
    # 6. Router Agent (full flow)
    print("\n🔄 TESTING ROUTER AGENT (FULL FLOW)")
    router_payload = {
        "id": f"{session_id}-router",
        "message": {
            "role": "user",
            "parts": [{"text": query}]  # Original query
        }
    }
    
    router_response_text, router_response_full = call_agent_with_details(
        "Router", 
        "http://localhost:5006/tasks/send", 
        router_payload
    )
    
    results['router'] = {
        "result": router_response_text,
        "full_response": router_response_full
    }
    
    # Calculate total time
    total_time = time.time() - start_time
    
    # Final results summary
    print(f"\n{'='*80}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*80}")
    print(f"Original query: '{query}'")
    print(f"Total processing time: {total_time:.2f} seconds")
    
    if 'language' in results and results['language'] != 'en':
        print(f"Detected language: {results['language']}")
        if 'translator' in results:
            print(f"Translated query: '{results['translator']['result']}'")
    
    # Display memory context with better formatting
    if memory_context and not memory_context.startswith("Error:"):
        print(f"\nMemory context:\n{memory_context}")
    else:
        print("\nMemory context: No relevant context found")
    
    # Display complete search results
    if search_results and not search_results.startswith("Error:"):
        print(f"\nSearch results:\n{search_results}")
    else:
        print("\nSearch results: Failed to retrieve search results")
    
    # Display complete final and router responses
    print(f"\nFinal agent response:\n{final_response_text}")
    print(f"\nRouter response:\n{router_response_text}")
    
    return results

if __name__ == "__main__":
    # Get query from command line argument or use a default
    query = sys.argv[1] if len(sys.argv) > 1 else "What is the weather in Paris?"
    test_all_agents(query)