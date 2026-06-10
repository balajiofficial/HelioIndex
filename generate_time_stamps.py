from datetime import datetime, timedelta

def generate_timestamp_jpg_names(start: datetime, end: datetime, output_file: str = "files.txt") -> list[str]:
    """
    Generate JPG filenames (one per hour) between two dates and save them to a .txt file.
 
    Args:
        start:       Start datetime (inclusive).
        end:         End datetime (inclusive).
        output_file: Path to the text file where names will be saved (default: files.txt).
 
    Returns:
        List of generated filenames.
    """
    if start > end:
        raise ValueError("start must be before or equal to end")
 
    filenames = []
    current = start
 
    while current <= end:
        filenames.append(current.strftime("%Y%m%d_%H%M%S") + ".jpg")
        current += timedelta(minutes=1)
 
    with open(output_file, "w") as f:
        f.write("\n".join(filenames))
 
    return filenames
 

generate_timestamp_jpg_names(
    start=datetime(2025, 10, 1, 0, 0, 0),
    end=datetime(2026, 1, 2, 6, 0, 0),
    output_file="files.txt"   # optional, defaults to "files.txt"
)