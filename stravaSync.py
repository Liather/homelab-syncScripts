import json
import requests
import time 
import argparse
import psycopg2

parser = argparse.ArgumentParser()
parser.add_argument("--days", type=int, default=2)
args = parser.parse_args()

with open("config.json", "r") as jsonfile:
    configData = json.load(jsonfile)

CLIENT_ID = configData["strava"]["CLIENT_ID"]
CLIENT_SECRET = configData["strava"]["CLIENT_SECRET"]
REFRESH_TOKEN = configData["strava"]["REFRESH_TOKEN"]

DB_CONFIG = configData["postgres"]

def getAccessToken(client_id, client_secret, refresh_token):
    response = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    response.raise_for_status()
    data = response.json()
    if "access_token" not in data:
        print("LOG ACCESS TOKEN FAILURE")
    return data["access_token"]

def getActivities(accessToken, days):
    after = int(time.time()) - (days * 86400)
    allActivities = []
    page = 1

    while True:
        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {accessToken}"},
            params={"after": after, "per_page": 100, "page": page}
        )
        data = response.json()
        if not isinstance(data, list):
            print("Strava activities failed to fetch: {data}")
        if not data:
            break
        allActivities.extend(data)
        print(f"Fetch page {page} ({len(data)} activities)")
        page += 1
    return allActivities

def parseActivity(activity):
    distanceKM = round(activity["distance"] / 1000, 2)
    movingTimeSec = activity["moving_time"]
    paceSecPerKM = int(movingTimeSec / distanceKM) if distanceKM > 0 else 0
    mins = paceSecPerKM // 60
    secs = paceSecPerKM % 60

    return {
          "stravaid": str(activity["id"]),
          "date": activity["start_date_local"][:10],
          "name": activity["name"],
          "type": activity.get("sport_type") or activity.get("type"),
          "distancekm": distanceKM,
          "movingtimesec": movingTimeSec,
          "paceperkm": f"{mins}:{secs:02d}",
          "avghr": activity.get("average_heartrate"),
          "maxhr": activity.get("max_heartrate"),
          "sufferscore": activity.get("suffer_score"),
          "avgwatts": activity.get("average_watts"),
          "avgcadence": activity.get("average_cadence"),
          "elevationgainm": activity.get("total_elevation_gain"),
          "elevhighm": activity.get("elev_high"),
          "elevlowm": activity.get("elev_low"),
          "avgtempc": activity.get("average_temp"),
          "calorieskj": activity.get("calories"),
          "startepoch": int(activity["start_date_local"][:19].replace("T", " ").replace("-", "").replace(":", "")) if activity.get("start_date") else None,
      }

def main():
    accessToken = getAccessToken(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
    
    activities = getActivities(accessToken, args.days)

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    imported = 0
    skipped = 0

    for a in activities:
        activity = parseActivity(cursor, activity)
        if cursor.rowcount == 1:
            imported += 1
            print(f"Imported: {activity['date']} - {activity['name']} ({activty['distanceKM']}km)")
        else:
            skipped += 1
            print(f"Skipped (exists): {activity['date']} - {activity['name']}")
    
    conn.commit()
    cursor.close()
    conn.close()

    print(f"\nDone - {imported} imported, {skipped} skipped")

if __name__ == "__main__":
    main()