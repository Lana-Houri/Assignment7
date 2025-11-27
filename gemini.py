# gemini.py

from google.genai import Client

# Put your API key here
client = Client(api_key="AIzaSyAgoaqExo5chkg3DiYdmPF_AreuCS1tjYE")

print("Available models:")
for model in client.models.list():
    print("-", model.name)
