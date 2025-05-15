import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()


def get_config():
    """Безопасно загружает конфигурацию из переменных окружения"""
    return {
        'DATA_URL': os.environ['DATA_URL'],  # Обязательная переменная
        'HTTP_PROXY': os.environ.get('HTTP_PROXY'),
        'HTTPS_PROXY': os.environ.get('HTTPS_PROXY'),
        'OUTPUT_FILE': os.environ.get('OUTPUT_FILE', 'output.json')
    }


def extract_level(level_str):
    """Конвертирует значения высот в Flight Levels с точным округлением"""
    if not level_str:
        return 0

    if "AGL" in level_str or "AMSL" in level_str:
        meters = int(level_str.replace("AGL", "").replace("AMSL", ""))
        return round(meters / 30.48)  # Более точное округление
    elif "F" in level_str:
        return int(level_str.replace("F", ""))
    return 0


def fetch_xml_data(url):
    """Загружает данные с безопасной обработкой ошибок"""
    try:
        config = get_config()
        proxies = {
            "http": config['HTTP_PROXY'],
            "https": config['HTTPS_PROXY'],
        } if config['HTTP_PROXY'] or config['HTTPS_PROXY'] else None

        response = requests.get(
            url,
            proxies=proxies,
            timeout=15,
            verify=False,
            headers={'User-Agent': 'AirspaceDataProcessor/1.0'}
        )
        response.raise_for_status()
        return response.text
    except KeyError as e:
        print(f"Отсутствует обязательная переменная окружения: {e}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при загрузке данных: {e}")
        return None


def main():
    try:
        config = get_config()
        xml_data = fetch_xml_data(config['DATA_URL'])

        if not xml_data:
            raise Exception("Не удалось загрузить XML данные")

        root = ET.fromstring(xml_data)
        today = datetime.now(timezone.utc).date()
        areas = []

        for tra in root.findall("tra"):
            for target_date in [today, today + timedelta(days=1)]:
                if (zone_data := process_tra_zone(tra, target_date)):
                    areas.append(zone_data)

        result = {
            "notice_info": create_notice_info(),
            "areas": areas
        }

        with open(config['OUTPUT_FILE'], 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"Данные сохранены в {config['OUTPUT_FILE']}")

    except Exception as e:
        print(f"Критическая ошибка: {e}")
        exit(1)


def process_tra_zone(tra, target_date):
    """Вынесенная логика обработки зон"""
    try:
        zc = tra.findtext("zc", "").strip()
        if "UNNT" not in zc:
            return None

        start_datetime = datetime.strptime(
            tra.findtext("datefrom", ""),
            "%Y-%m-%dT%H:%MZ"
        ).replace(tzinfo=timezone.utc)

        end_datetime = datetime.strptime(
            tra.findtext("dateto", ""),
            "%Y-%m-%dT%H:%MZ"
        ).replace(tzinfo=timezone.utc)

        if start_datetime.date() <= target_date <= end_datetime.date():
            return {
                "name": tra.findtext("areacode", "").strip(),
                "minimum_fl": extract_level(tra.findtext("levelfrom")),
                "maximum_fl": extract_level(tra.findtext("levelto")),
                "start_datetime": start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_datetime": end_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "remark": get_remark(
                    tra.findtext("levelfrom", ""),
                    tra.findtext("levelto", "")
                ),
                "active_date": target_date.strftime("%Y-%m-%d")
            }
    except (ValueError, AttributeError) as e:
        print(f"Ошибка обработки зоны: {e}")
    return None


def get_remark(level_from, level_to):
    """Вынесенная логика определения remark"""
    remarks = {determine_remark(l) for l in [level_from, level_to] if l}
    return ", ".join(filter(None, remarks))


if __name__ == "__main__":
    main()