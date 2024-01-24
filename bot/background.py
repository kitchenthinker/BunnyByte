from flask import Flask, request
from threading import Thread


app = Flask(__name__)

@app.route('/')
def home():
  return "I'm alive"

def run():
  app.run(host="https://common-aubine-bunnybytedev.koyeb.app")

def keep_alive():
  t = Thread(target=run)
  t.start()
