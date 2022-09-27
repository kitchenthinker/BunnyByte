# API_KEYS
import os
from dotenv import load_dotenv

file_path = "../../.discord_env"
if os.path.exists(file_path):
    configs = load_dotenv(file_path)

# DISCORD
BUNNYBYTE_TOKEN = os.getenv("DISCORD_BUNNYBYTE_TOKEN")

# MYSQL
mSQL_H = os.getenv("mSQL_h")
mSQL_L = os.getenv("mSQL_l")
mSQL_P = os.getenv("mSQL_p")
mSQL_DB = os.getenv("mSQL_db")
