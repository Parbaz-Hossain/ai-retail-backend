from datetime import date, datetime
from typing import Any, Dict
import re

# Your serialize/deserialize functions (keep them as provided earlier)
def serialize_dates(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively convert date/datetime objects to ISO format strings"""
    def convert_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, dict):
            return serialize_dates(value)
        elif isinstance(value, list):
            return [convert_value(item) for item in value]
        return value
    
    serialized = {}
    for key, value in data.items():
        serialized[key] = convert_value(value)
    return serialized


def deserialize_dates(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively convert ISO format strings back to date/datetime objects"""
    ISO_DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    ISO_DATETIME_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')
    
    def convert_value(value: Any) -> Any:
        if isinstance(value, str):
            if ISO_DATETIME_PATTERN.match(value):
                try:
                    return datetime.fromisoformat(value.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    return value
            elif ISO_DATE_PATTERN.match(value):
                try:
                    return datetime.fromisoformat(value).date()
                except (ValueError, AttributeError):
                    return value
        elif isinstance(value, dict):
            return deserialize_dates(value)
        elif isinstance(value, list):
            return [convert_value(item) for item in value]
        return value
    
    deserialized = {}
    for key, value in data.items():
        deserialized[key] = convert_value(value)
    return deserialized