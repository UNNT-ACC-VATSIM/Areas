import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, timedelta, timezone


def extract_level(level_str):
    """Извлекает числовое значение уровня из строки"""
    if not level_str:
        return 0

    if "AGL" in level_str or "AMSL" in level_str:
        numeric_value = int(level_str.replace("AGL", "").replace("AMSL", ""))
        return int((numeric_value * 3) / 100)
    elif "F" in level_str:
        return int(level_str.replace("F", ""))
    return 0


def determine_remark(level_str):
    """Определяет примечание (remark) на основе формата уровня"""
    if not level_str:
        return ""

    if "AGL" in level_str:
        return "MAGL"
    elif "AMSL" in level_str:
        return "MAMSL"
    elif "F" in level_str:
        return "FL"
    return ""


def fetch_xml_data(url, proxy_settings=None):
    """Загружает XML данные по указанному URL с использованием прокси"""
    try:
        proxies = {
            "http": proxy_settings.get("http") if proxy_settings else None,
            "https": proxy_settings.get("https") if proxy_settings else None,
        } if proxy_settings else None

        response = requests.get(
            url,
            proxies=proxies,
            timeout=10,
            verify=False  # Отключаем проверку SSL для некоторых прокси
        )
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке данных: {e}")
        return None


def process_tra_zone(tra, target_date):
    """Обрабатывает зону TRA и возвращает данные, если активна в target_date"""
    zc = tra.find("zc").text.strip() if tra.find("zc") is not None else ""

    # Фильтруем только зоны с "UNNT" в теге <zc>
    if "UNNT" not in zc:
        return None

    area_code = tra.find("areacode").text.strip() if tra.find("areacode") is not None else ""
    level_from = tra.find("levelfrom").text if tra.find("levelfrom") is not None else ""
    level_to = tra.find("levelto").text if tra.find("levelto") is not None else ""
    date_from = tra.find("datefrom").text if tra.find("datefrom") is not None else ""
    date_to = tra.find("dateto").text if tra.find("dateto") is not None else ""

    try:
        start_datetime = datetime.strptime(date_from, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        end_datetime = datetime.strptime(date_to, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except ValueError:
        print(f"Ошибка при парсинге времени: date_from={date_from}, date_to={date_to}")
        return None

    # Проверяем, что зона активна в целевую дату
    if start_datetime.date() <= target_date <= end_datetime.date():
        # Форматируем дату-время
        start_datetime_iso = start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_datetime_iso = end_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Определяем примечание
        remark_from = determine_remark(level_from)
        remark_to = determine_remark(level_to)
        remark = remark_from if remark_from == remark_to else f"{remark_from}, {remark_to}".strip(", ")

        return {
            "name": area_code,
            "minimum_fl": extract_level(level_from),
            "maximum_fl": extract_level(level_to),
            "start_datetime": start_datetime_iso,
            "end_datetime": end_datetime_iso,
            "remark": remark,
            "active_date": target_date.strftime("%Y-%m-%d")  # Добавляем дату активности
        }
    return None


def main():
    # Настройки прокси (можно задать через переменные окружения или конфиг)
    PROXY_SETTINGS = {
        "http": "http://eRybc5:9SMtq5@194.26.207.200:8000",  # Замените на ваш HTTP прокси
        "https": "http://eRybc5:9SMtq5@194.26.207.200:8000",  # Замените на ваш HTTPS прокси
    }

    # URL для загрузки XML данных
    url = "https://app.matfmc.ru/AirspaceAvailabilityBulletinXML/tra"

    # Загружаем XML данные с использованием прокси
    xml_data = fetch_xml_data(url, proxy_settings=PROXY_SETTINGS)

    if not xml_data:
        print("Не удалось загрузить XML данные.")
        return

    try:
        # Парсим XML
        root = ET.fromstring(xml_data)
        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)
        areas = []

        # Обрабатываем каждую зону (tra)
        for tra in root.findall("tra"):
            # Проверяем для сегодня
            today_data = process_tra_zone(tra, today)
            if today_data:
                areas.append(today_data)

            # Проверяем для завтра
            tomorrow_data = process_tra_zone(tra, tomorrow)
            if tomorrow_data:
                areas.append(tomorrow_data)

        # Формируем финальную структуру JSON
        current_time = datetime.now(timezone.utc)
        valid_wef = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        valid_til = (current_time + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        result = {
            "notice_info": {
                "valid_wef": valid_wef,
                "valid_til": valid_til,
                "released_on": valid_wef
            },
            "areas": areas
        }

        # Сохраняем в файл
        with open("output.json", "w", encoding="utf-8") as json_file:
            json.dump(result, json_file, indent=4, ensure_ascii=False)

        print("Данные успешно сохранены в output.json")

    except Exception as e:
        print(f"Ошибка при обработке XML данных: {e}")


if __name__ == "__main__":
    main()