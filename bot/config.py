# API_KEYS
import os
from dotenv import load_dotenv

config = load_dotenv('../discord.env')

# DISCORD
BUNNYBYTE_TOKEN = os.getenv("DISCORD_BUNNYBYTE_TOKEN")

# MYSQL
mSQL_H = os.getenv("mSQL_h")
mSQL_L = os.getenv("mSQL_l")
mSQL_P = os.getenv("mSQL_p")