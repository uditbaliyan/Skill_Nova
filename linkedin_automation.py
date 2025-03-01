import requests
from datetime import datetime

a=1
print(f"{a } ----- {a }")
# Define the dates as strings
start = '2024-02-18'
curr_date =str(datetime.date(datetime.now()))

# Convert the strings to datetime objects
difference=datetime.strptime(curr_date, '%Y-%m-%d')-datetime.strptime(start, '%Y-%m-%d')

# Extract the number of days from the difference
num_days = difference.days

a=(f"Day {num_days} Of Daily Python Problems \n\n#PythonProgramming #Coding #PythonCodeSnippet #DailyPythonCoding")

# Define the JSON payload
data = {
    "author": "urn:li:person:kWsy4_KjQW",
    "lifecycleState": "PUBLISHED",
    "specificContent": {
        "com.linkedin.ugc.ShareContent": {
            "shareCommentary": {
                "text": a
            },
            "shareMediaCategory": "NONE"
        }
    },
    "visibility": {
        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
    }
}

# Define the LinkedIn API endpoint
api_url = 'https://api.linkedin.com/v2/ugcPosts'

# Define your access token
access_token="AQXtQNzhYYPNHoaMzfCw-wCNCIYaChrQswxoPQy7eY51hHv3TbpmQ1ENlCPoRjydgZjKN-kQeKkV7Zb-h2u2VugQ00EW9c0JhUiYFY63GS7mPt_G7iZ-Q1EnYrntxv-SZ2bNZ5p5PH8G6cJibRtE1LxFG6DY-z7L_ZKh5505iS5X3PfZD5ijzYuKBJhZWrpnTvJ1TFDv0FZzWsu7Zzjg7F0fvWME1cAdRcUhEevKG63Sx_32s-Gtwwd_QsXXTAWyFqGTm6VidvCC0mQF7nHmbtb2SmcAQgUVVCnzJRT7lfv6WqTe3Z8gyQh_rfE5qIMLKehk0QuEwe5_tGr5m8Lx4WzmwJCi6w"

# Define headers
headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + access_token
}

# Send POST request to LinkedIn API
response = requests.post(api_url, json=data, headers=headers)

# Check if request was successful
if response.status_code == 201:
    print("Post successfully created on LinkedIn!")
else:
    print("Failed to create post. Status code:", response.status_code)
    print("Error message:", response.text)
