import json
import time
from datetime import datetime
import pytz

tz = pytz.timezone('America/Toronto')

def get_date_time(decoded_str_date):
	return datetime.fromtimestamp(float(decoded_str_date), tz).strftime('%Y-%m-%dT%H:%M:%S') if decoded_str_date != "" else None

def convert_to_int(decoded_str):
	return int(decoded_str) if decoded_str != "" else None

def convert_to_bool(decoded_bool_str):
	return True if decoded_bool_str == "1" else False

def convert_to_json(decoded_json_str):
	return json.loads(decoded_json_str)