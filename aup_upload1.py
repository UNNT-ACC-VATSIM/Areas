import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

class AirspaceProcessor:
    def __init__(self):
        self.config = {
            'DATA_URL': os.getenv('DATA_URL'),
            'HTTP_PROXY': os.getenv('HTTP_PROXY'),
            'HTTPS_PROXY': os.getenv('HTTPS_PROXY'),
            'OUTPUT_FILE': os.getenv('OUTPUT_FILE', 'output.json')
        }
        self.validate_config()

    def validate_config(self):
        if not self.config['DATA_URL']:
            raise ValueError("DATA_URL must be set in environment variables")

    def extract_level(self, level_str):
        """Конвертация высот в Flight Levels"""
        if not level_str:
            return 0

        if "AGL" in level_str or "AMSL" in level_str:
            meters = int(level_str.replace("AGL", "").replace("AMSL", ""))
            return round(meters / 30.48)  # 1 FL = 30.48 метров
        elif "F" in level_str:
            return int(level_str.replace("F", ""))
        return 0

    def determine_remark(self, level_str):
        """Определение примечания к высоте"""
        if not level_str:
            return ""

        if "AGL" in level_str:
            return "MAGL"
        elif "AMSL" in level_str:
            return "MAMSL"
        elif "F" in level_str:
            return "FL"
        return ""

    def fetch_xml_data(self):
        """Загрузка XML данных с прокси-поддержкой"""
        try:
            proxies = {
                "http": self.config['HTTP_PROXY'],
                "https": self.config['HTTPS_PROXY'],
            } if self.config['HTTP_PROXY'] or self.config['HTTPS_PROXY'] else None

            response = requests.get(
                self.config['DATA_URL'],
                proxies=proxies,
                timeout=15,
                verify=False
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Ошибка загрузки данных: {e}")
            return None

    def process_zone(self, tra, target_date):
        """Обработка одной зоны"""
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
                level_from = tra.findtext("levelfrom", "")
                level_to = tra.findtext("levelto", "")
                
                return {
                    "name": tra.findtext("areacode", "").strip(),
                    "minimum_fl": self.extract_level(level_from),
                    "maximum_fl": self.extract_level(level_to),
                    "start_datetime": start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_datetime": end_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "remark": self.determine_remark(level_from),
                    "active_date": target_date.strftime("%Y-%m-%d")
                }
        except Exception as e:
            print(f"Ошибка обработки зоны: {e}")
        return None

    def generate_output(self):
        """Генерация выходного JSON"""
        xml_data = self.fetch_xml_data()
        if not xml_data:
            return None

        root = ET.fromstring(xml_data)
        today = datetime.now(timezone.utc).date()
        areas = []

        for tra in root.findall("tra"):
            for target_date in [today, today + timedelta(days=1)]:
                if zone_data := self.process_zone(tra, target_date):
                    areas.append(zone_data)

        current_time = datetime.now(timezone.utc)
        return {
            "notice_info": {
                "valid_wef": current_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "valid_til": (current_time + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "released_on": current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            },
            "areas": areas
        }

    def save_to_file(self, data):
        """Сохранение данных в файл"""
        with open(self.config['OUTPUT_FILE'], 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Данные сохранены в {self.config['OUTPUT_FILE']}")

def main():
    try:
        processor = AirspaceProcessor()
        output_data = processor.generate_output()
        
        if output_data:
            processor.save_to_file(output_data)
        else:
            raise Exception("Не удалось сгенерировать выходные данные")
            
    except Exception as e:
        print(f"Ошибка: {e}")
        exit(1)

if __name__ == "__main__":
    main()
