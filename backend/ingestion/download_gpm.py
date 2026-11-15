
import earthaccess
from pathlib import Path

from config.ethiopia import ETHIOPIA


def download_gpm_data():
    bounds = ETHIOPIA["bounds"]

    # Authenticate
    earthaccess.login(
        strategy="interactive",
        persist=True
    )

    # Search for observations
    granules = earthaccess.search_data(
        short_name="GPM_3IMERGDF",
        version="07",
        temporal=("2025-01-01", "2025-01-07"),
        bounding_box=(
            bounds["west"],
            bounds["south"],
            bounds["east"],
            bounds["north"]
        ),
        count=5
    )

    if not granules:
        print("No GPM observations found.")
        return

    # Download into our raw data directory
    output_dir = Path("data/raw/gpm")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(granules)} observations...")

    downloaded = earthaccess.download(
        granules,
        local_path=str(output_dir)
    )

    print(f"\nDownloaded {len(downloaded)} files.")

    for file in downloaded:
        print(file)


if __name__ == "__main__":
    download_gpm_data()
