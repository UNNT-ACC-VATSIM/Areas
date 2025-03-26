import json
import requests
from datetime import datetime, timedelta, timezone
import os

# Функция для преобразования UNIX-времени в строку ISO 8601
def unix_to_iso(unix_time):
    return datetime.fromtimestamp(unix_time, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

# Функция для преобразования высоты в зависимости от единиц измерения
def convert_height(value, unit):
    if unit == "ftqne":
        return round(value / 100)
    elif unit in ["mamsl", "magl"]:
        return round((value * 3.28) / 100)
    else:
        print(f"Неизвестная единица измерения: {unit}")
        return value

# Функция для генерации valid_wef и valid_til
def generate_valid_times():
    # Текущая дата и время в формате ISO 8601
    valid_wef = datetime.now(timezone.utc)
    valid_til = valid_wef + timedelta(hours=3)

    # Преобразуем в строки ISO 8601
    valid_wef_iso = valid_wef.strftime('%Y-%m-%dT%H:%M:%SZ')
    valid_til_iso = valid_til.strftime('%Y-%m-%dT%H:%M:%SZ')

    return valid_wef_iso, valid_til_iso

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

# Переменная для хранения времени окончания последней зоны
latest_end_time = None

# Обработка каждой зоны
for zone in input_data["data"]:
    areas_time = zone.get("areas_time", "")
    time_ranges = areas_time.split("\n")[1:-1]  # Убираем первую и последнюю пустые строки

    for time_range in time_ranges:
        try:
            # Очищаем строку от лишнего текста (например, "Работа утверждена:")
            cleaned_time_range = time_range.strip()
            
            # Проверяем, содержит ли строка временной диапазон
            if "-" not in cleaned_time_range:
                continue  # Пропускаем строки без временного диапазона
            
            # Разделяем строку на дату и временной интервал
            parts = cleaned_time_range.split(" ")
            if len(parts) < 2:
                continue  # Пропускаем строки с некорректным форматом
            
            date_part = parts[0]
            time_interval = parts[1]

            # Проверяем формат даты
            if "-" in date_part and "-" in time_interval:
                # Формат "датаначало времяначало-датаокончания времяокончания"
                start_date_str, end_date_str = date_part.split("-")
                start_time_str, end_time_str = time_interval.split("-")

                start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
                end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()

            elif "-" in date_part:
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

            # Проверяем формат времени (HH:MM)
            if not (len(start_time_str) == 5 and len(end_time_str) == 5 and
                    start_time_str[2] == ":" and end_time_str[2] == ":"):
                raise ValueError("Некорректный формат времени")

        except ValueError as e:
            print(f"Ошибка обработки временного интервала: {e}")
            continue  # Пропускаем некорректные данные

        # Проверяем, попадает ли текущая дата в диапазон
        if not (start_date <= next_date and end_date >= current_date):
            continue

        current_date_in_range = max(start_date, current_date)
        iteration_count = 0  # Счетчик итераций для защиты от зацикливания

        while current_date_in_range <= min(end_date, next_date):
            # Защита от зацикливания
            if iteration_count > 365:  # Максимум 365 дней
                print("Обнаружено зацикливание. Прерывание цикла.")
                break

            # Формируем строки day_start и day_end
            day_start = current_date_in_range.strftime("%Y-%m-%d") + "T" + start_time_str + ":00Z"
            day_end = current_date_in_range.strftime("%Y-%m-%d") + "T" + end_time_str + ":00Z"

            # Проверяем корректность форматов
            try:
                datetime.strptime(day_start, "%Y-%m-%dT%H:%M:%SZ")
                datetime.strptime(day_end, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError as e:
                print(f"Ошибка формата времени: {e}")
                break  # Прерываем цикл при ошибке формата

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

            # Переходим к следующей дате
            current_date_in_range += timedelta(days=1)
            iteration_count += 1

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
