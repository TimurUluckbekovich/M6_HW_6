import os
from dotenv import load_dotenv

load_dotenv()

if os.getenv("PRODUCTION", "False").lower() == "true":
    from .production import *
else:
    from .development import *