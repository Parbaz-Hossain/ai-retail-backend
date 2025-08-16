from datetime import datetime, time, timedelta

def is_valid_shift(start_time: time, end_time: time) -> bool:
    """Check if shift duration is positive, even across midnight."""
    dt_start = datetime.combine(datetime.today(), start_time)
    dt_end = datetime.combine(datetime.today(), end_time)
    
    # If end time is earlier than start, assume it's next day
    if dt_end <= dt_start:
        dt_end += timedelta(days=1)
    
    return (dt_end - dt_start).total_seconds() > 0
