import requests

def detect_location(ip):

    try:
        data = requests.get(
            f"http://ip-api.com/json/{ip}"
        ).json()

        return data

    except:

        return None