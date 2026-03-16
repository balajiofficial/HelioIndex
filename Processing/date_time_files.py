from datetime import datetime, timedelta

start = datetime(2026, 1, 15, 2, 0, 0)
end = datetime(2026, 3, 15, 2, 0, 0)

base_path = "/Users/balajikannan/Documents/HelioIndex/input"

files = []
current = start
while current <= end:
    filename = current.strftime("%Y%m%d_%H%M%S")
    files.append(f"{base_path}/{filename}.jpg")
    current += timedelta(seconds=1)

output_file = "file_list.txt"
with open(output_file, "w") as f:
    f.write("\n".join(files))

print(f"Generated {len(files):,} file paths -> {output_file}")