from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
for m in OpenAI().models.list():
    print(m.id)