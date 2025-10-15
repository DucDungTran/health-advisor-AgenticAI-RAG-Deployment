import requests

query = {
  "prompt": "I'm a busy person who wants healthy, easy-to-make breakfasts. I like oatmeal and eggs. Please suggest two breakfast options, including their ingredients and calorie counts."
}

url = "http://localhost:9000/advise"

response = requests.post(url, json=query)

print(response.json()['output'])