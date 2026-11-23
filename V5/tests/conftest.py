import os

# Tests must never call a real LLM (slow, uses your quota). Setting these BEFORE app.py is imported
# stops load_dotenv() from loading the real key out of .env.
os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_REPLY"] = "0"