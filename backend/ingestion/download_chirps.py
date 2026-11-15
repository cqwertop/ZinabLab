
from pathlib import Path
import requests
import time

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "chirps"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = (
    "https://data.chc.ucsb.edu/products/CHIRPS/"
    "v3.0/monthly/africa/tifs/"
)

START_YEAR = 2015
END_YEAR = 2024


def download_file(session, year, month):
    filename = f"chirps-v3.0.{year}.{month:02d}.tif"
    output_file = OUTPUT_DIR / filename
    url = BASE_URL + filename

    if output_file.exists() and output_file.stat().st_size > 0:
        print(f"Already downloaded: {filename}")
        return True

    for attempt in range(3):
        try:
            print(f"Downloading: {filename}")

            with session.get(
                url, stream=True, timeout=(20, 180)
            ) as response:
                response.raise_for_status()

                temp_file = output_file.with_suffix(".tif.part")

                with open(temp_file, "wb") as file:
                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if chunk:
                            file.write(chunk)

                temp_file.replace(output_file)

            print(f"Downloaded: {filename}")
            return True

        except Exception as error:
            print(f"Attempt {attempt + 1} failed: {error}")

            if temp_file.exists():
                temp_file.unlink()

            time.sleep(3)

    print(f"FAILED: {filename}")
    return False


def main():
    successful = 0
    failed = []

    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "DancingWithTheSARs/1.0"
        })

        for year in range(START_YEAR, END_YEAR + 1):
            for month in range(1, 13):
                if download_file(session, year, month):
                    successful += 1
                else:
                    failed.append(f"{year}-{month:02d}")

    print("\nDOWNLOAD SUMMARY")
    print("Successful:", successful)
    print("Failed:", len(failed))

    if failed:
        print("Failed months:", failed)


if __name__ == "__main__":
    main()
