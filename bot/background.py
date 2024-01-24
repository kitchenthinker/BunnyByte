from flask import Flask, request
from threading import Thread


app = Flask(__name__)

@app.route('/')
def home():
  return "I'm alive"

def run():
  app.run(port=8000)

def keep_alive():
  t = Thread(target=run)
  t.start()
