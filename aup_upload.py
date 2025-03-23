import json
import requests
from datetime import datetime, timedelta, timezone
import os

def unix_to_iso(unix_time):
    return datetime.fromtimestamp(unix_time, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def convert_height(value, unit):
    if unit == "ftqne":
        return round(value / 100)
    elif unit in ["mamsl", "magl"]:
        return round((value * 3) / 100)
    else:
        print(f"Неизвестная единица измерения: {unit}")
        return value

proxies = {
    "http": os.getenv("PROXY_URL"),
    "https": os.getenv("PROXY_HTTPS_URL")
}

url = os.getenv("API_URL_SPPI_IVP_RF")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Authorization": f"Bearer {os.getenv('API_TOKEN')}"
}

try:
    response = requests.get(url, headers=headers, proxies=proxies)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"Статус код: {response.status_code}")
    print(f"Текст ответа: {response.text}")
    raise Exception(f"Ошибка при загрузке данных через прокси: {e}")

input_data = response.json()

current_date = datetime.now(timezone.utc).date()
next_date = current_date + timedelta(days=1)

output_areas = []
latest_end_time = None

for zone in input_data["data"]:
    areas_time = zone.get("areas_time", "")
    time_ranges = areas_time.split("\n")[1:-1]
    
    for time_range in time_ranges:
        try:
            date_range, time_interval = time_range.strip().split(" ")
            start_date_str, end_date_str = date_range.split("-")
            start_time_str, end_time_str = time_interval.split("-")
        except ValueError:
            continue
        
        try:
            start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
            end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()
        except ValueError:
            continue

        if not (start_date <= next_date and end_date >= current_date):
            continue
        
        current_date_in_range = max(start_date, current_date)
        while current_date_in_range <= min(end_date, next_date):
            day_start = current_date_in_range.strftime("%Y-%m-%d") + "T" + start_time_str + ":00Z"
            day_end = current_date_in_range.strftime("%Y-%m-%d") + "T" + end_time_str + ":00Z"
            
            low_level_unit = zone["low_level"]["unit"]
            high_level_unit = zone["high_level"]["unit"]
            
            minimum_fl = convert_height(zone["low_level"]["value"], low_level_unit)
            maximum_fl = convert_height(zone["high_level"]["value"], high_level_unit)
            
            output_areas.append({
                "name": zone["name"],
                "minimum_fl": minimum_fl,
                "maximum_fl": maximum_fl,
                "start_datetime": day_start,
                "end_datetime": day_end,
                "remark": low_level_unit.upper()
            })
            
            latest_end_time = max(
                latest_end_time or datetime.min.replace(tzinfo=timezone.utc),
                datetime.strptime(day_end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            )
            
            current_date_in_range += timedelta(days=1)

output_data = {
    "notice_info": {
        "released_on": unix_to_iso(int(datetime.now(timezone.utc).timestamp()))
    },
    "areas": output_areas
}

with open("output.json", "w", encoding="utf-8") as file:
    json.dump(output_data, file, ensure_ascii=False, indent=4)

print("Итоговый файл output.json:")
with open("output.json", "r", encoding="utf-8") as file:
    print(file.read())
