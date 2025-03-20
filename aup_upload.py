import os
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, timedelta, timezone

def extract_level(level_str):
    if not level_str:
        return 0

    if "AGL" in level_str or "AMSL" in level_str:
        numeric_value = int(level_str.replace("AGL", "").replace("AMSL", ""))
        return int((numeric_value * 3) / 100)
    elif "F" in level_str:
        return int(level_str.replace("F", ""))
    return 0

def determine_remark(level_str):
    if not level_str:
        return ""

    if "AGL" in level_str:
        return "AGL"
    elif "AMSL" in level_str:
        return "AMSL"
    elif "F" in level_str:
        return "FL"
    else:
        return ""

def fetch_xml_data(url):
    proxy_url = os.getenv("PROXY_URL")
    if not proxy_url:
        print("Ошибка: Переменная окружения PROXY_URL не найдена.")
        return None

    proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }

    try:
        response = requests.get(url, proxies=proxies, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке данных: {e}")
        return None

def main():
    api_url = os.getenv("API_URL_SPPI_IVP_RF")
    if not api_url:
        print("Ошибка: Переменная окружения API_URL_SPPI_IVP_RF не найдена.")
        exit(1)

    xml_data = fetch_xml_data(api_url)
    if not xml_data:
        print("Не удалось загрузить XML данные.")
        exit(1)

    try:
        # Парсим XML
        root = ET.fromstring(xml_data)

        # Получаем текущую дату и время
        current_utc_time = datetime.now(timezone.utc)
        today = current_utc_time.date()

        areas = []

        for tra in root.findall("tra"):
            zc = tra.find("zc").text.strip() if tra.find("zc") is not None else ""

            if "UNNT" not in zc:
                continue

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
                continue

            if start_datetime.date() <= today <= end_datetime.date():
                if start_datetime <= current_utc_time <= end_datetime:
                    start_datetime_iso = start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
                    end_datetime_iso = end_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")

                    remark_from = determine_remark(level_from)
                    remark_to = determine_remark(level_to)

                    if remark_from == remark_to:
                        remark = remark_from
                    else:
                        remark = f"{remark_from}, {remark_to}".strip(", ")

                    areas.append({
                        "name": area_code,
                        "minimum_fl": extract_level(level_from),
                        "maximum_fl": extract_level(level_to),
                        "start_datetime": start_datetime_iso,
                        "end_datetime": end_datetime_iso,
                        "remark": remark
                    })

        valid_wef = current_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        valid_til = (current_utc_time + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        released_on = valid_wef

        result = {
            "notice_info": {
                "valid_wef": valid_wef,
                "valid_til": valid_til,
                "released_on": released_on
            },
            "areas": areas
        }

        with open("output.json", "w", encoding="utf-8") as json_file:
            json.dump(result, json_file, indent=4, ensure_ascii=False)

        print("Данные успешно сохранены в output.json")
    except Exception as e:
        print(f"Ошибка при обработке XML данных: {e}")


if __name__ == "__main__":
    main()
