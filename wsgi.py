from dotenv import load_dotenv

# 1) Load .env into the process environmrnt 
load_dotenv()

# 2) Then import and build the app, wich will read from os.environ
from app import create_app

app = create_app()