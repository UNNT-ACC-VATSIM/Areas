import json
import requests
from datetime import datetime, timedelta, timezone
import os
import re

# Функция для преобразования UNIX-времени в строку ISO 8601
def unix_to_iso(unix_time):
    return datetime.fromtimestamp(unix_time, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# Функция для преобразования высоты в зависимости от единиц измерения
def convert_height(value, unit):
    if unit == "ftqne":
        return round(value / 100)
    elif unit in ["mamsl", "magl"]:
        return round((value * 3.280839895) / 100)
    else:
        print(f"Неизвестная единица измерения: {unit}")
        return value

# Функция для удаления текста в скобках
def remove_bracketed_text(text):
    return re.sub(r'\([^)]*\)', '', text).strip()

# Функция для генерации valid_wef и valid_til
def generate_valid_times():
    valid_wef = datetime.now(timezone.utc)
    valid_til = valid_wef + timedelta(hours=3)
    return valid_wef.strftime('%Y-%m-%dT%H:%M:%SZ'), valid_til.strftime('%Y-%m-%dT%H:%M:%SZ')

# Настройки прокси
proxies = {
    "http": os.getenv("PROXY_URL"),
    "https": os.getenv("PROXY_HTTPS_URL")
}

# URL для получения исходных данных
url = os.getenv("API_URL_SPPI_IVP_RF")

# Заголовки
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Authorization": f"Bearer {os.getenv('API_TOKEN')}"
}

# Загрузка данных с сервера через прокси
try:
    response = requests.get(url, headers=headers, proxies=proxies)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"Статус код: {response.status_code}")
    print(f"Текст ответа: {response.text}")
    raise Exception(f"Ошибка при загрузке данных через прокси: {e}")

input_data = response.json()

# Определяем текущую дату и дату следующего дня
current_date = datetime.now(timezone.utc).date()
next_date = current_date + timedelta(days=1)

# Создаем список для хранения всех зон
output_areas = []

# Обработка каждой зоны
for zone in input_data["data"]:
    areas_time = zone.get("areas_time", "")
    time_ranges = areas_time.split("\n")[1:-1]  # Убираем первую и последнюю пустые строки

    for time_range in time_ranges:
        try:
            # Удаляем лишние пробелы и текст в скобках
            time_range = remove_bracketed_text(time_range.strip())
            if not time_range:
                continue  # Пропускаем пустые строки

            # Проверяем формат "дата времяначало-дата времяокончания"
            if "-" in time_range and " " in time_range:
                parts = time_range.split("-")
                if len(parts) == 2 and " " in parts[0] and " " in parts[1]:
                    # Разделяем дату и время для начала и конца
                    start_part, end_part = parts
                    start_date_str, start_time_str = start_part.split(" ")
                    end_date_str, end_time_str = end_part.split(" ")

                    # Преобразуем строки в объекты datetime
                    start_datetime = datetime.strptime(f"{start_date_str} {start_time_str}", "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
                    end_datetime = datetime.strptime(f"{end_date_str} {end_time_str}", "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)

                    # Проверяем, попадает ли текущая дата в диапазон
                    if not (start_datetime.date() <= next_date and end_datetime.date() >= current_date):
                        continue

                    # Добавляем зону в выходной список
                    low_level_unit = zone["low_level"]["unit"]
                    high_level_unit = zone["high_level"]["unit"]

                    output_areas.append({
                        "name": zone["name"],
                        "minimum_fl": convert_height(zone["low_level"]["value"], low_level_unit),
                        "maximum_fl": convert_height(zone["high_level"]["value"], high_level_unit),
                        "start_datetime": start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "end_datetime": end_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "remark": low_level_unit.upper()
                    })
                    continue

            # Обработка других форматов (например, "дата-дата времяначало-времяокончания")
            date_part, time_interval = time_range.split(" ")

            if "-" in date_part:
                # Формат "дата-дата времяначало-времяокончания"
                start_date_str, end_date_str = date_part.split("-")
                start_time_str, end_time_str = time_interval.split("-")

                start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
                end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()
            else:
                # Формат "дата времяначало-времяокончания"
                start_date_str = end_date_str = date_part
                start_time_str, end_time_str = time_interval.split("-")

                start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
                end_date = start_date  # Начальная и конечная дата совпадают

            # Проверяем, попадает ли текущая дата в диапазон
            if not (start_date <= next_date and end_date >= current_date):
                continue

            current_date_in_range = max(start_date, current_date)
            while current_date_in_range <= min(end_date, next_date):
                day_start = current_date_in_range.strftime("%Y-%m-%d") + "T" + start_time_str + ":00Z"
                day_end = current_date_in_range.strftime("%Y-%m-%d") + "T" + end_time_str + ":00Z"

                low_level_unit = zone["low_level"]["unit"]
                high_level_unit = zone["high_level"]["unit"]

                output_areas.append({
                    "name": zone["name"],
                    "minimum_fl": convert_height(zone["low_level"]["value"], low_level_unit),
                    "maximum_fl": convert_height(zone["high_level"]["value"], high_level_unit),
                    "start_datetime": day_start,
                    "end_datetime": day_end,
                    "remark": low_level_unit.upper()
                })

                current_date_in_range += timedelta(days=1)

        except ValueError as e:
            print(f"Ошибка при обработке временного интервала '{time_range}': {e}")
            continue

# Генерация valid_wef и valid_til
valid_wef, valid_til = generate_valid_times()

# Формируем итоговый JSON
output_data = {
    "notice_info": {
        "released_on": unix_to_iso(int(datetime.now(timezone.utc).timestamp())),
        "valid_wef": valid_wef,
        "valid_til": valid_til
    },
    "areas": output_areas
}

# Запись результата в файл output.json
with open("output.json", "w", encoding="utf-8") as file:
    json.dump(output_data, file, ensure_ascii=False, indent=4)

# Вывод содержимого файла output.json
print("Итоговый файл output.json:")
with open("output.json", "r", encoding="utf-8") as file:
    print(file.read())
