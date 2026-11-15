
import earthaccess

from config.ethiopia import ETHIOPIA


def search_gpm_data():
    print("Connecting to NASA Earthdata...")

    # Authenticate with your NASA Earthdata account
    earthaccess.login(
        strategy="interactive",
        persist=True
    )

    bounds = ETHIOPIA["bounds"]

    print("Searching for GPM rainfall observations...")

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

    print(f"\nFound {len(granules)} GPM observations.")

    for index, granule in enumerate(granules, start=1):
        print(f"\nObservation {index}:")
        print(granule)

    return granules


if __name__ == "__main__":
    search_gpm_data()
