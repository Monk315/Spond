import argparse
import asyncio
import csv
from pathlib import Path

from config import club_id, password, username

from spond.club import SpondClub

EXPORT_DIRPATH = Path("./exports")

parser = argparse.ArgumentParser(
    description="Fetches club members from Spond Club (club/v1/members) and exports to club_members.csv"
)
parser.add_argument(
    "-u",
    "--unprocessed",
    help="Only fetch unprocessed (pending) members",
    action="store_true",
)
parser.add_argument(
    "-d",
    "--include-deleted",
    help="Include deactivated/deleted members",
    action="store_true",
)

args = parser.parse_args()


async def main() -> None:
    s = SpondClub(username=username, password=password)
    try:
        target_club_id = club_id
        if not target_club_id or target_club_id == "1234567890":
            clubs = await s.get_clubs()
            if not clubs:
                print("No Spond Clubs found for this account.")
                return
            target_club_id = clubs[0]["id"]
            print(
                f"Using discovered club: {clubs[0].get('name')} (id={target_club_id})"
            )

        if args.unprocessed:
            members = await s.get_members(
                club_id=target_club_id,
                include_processed=False,
                include_unprocessed=True,
                include_deleted=args.include_deleted,
            )
        elif args.include_deleted:
            members = await s.get_members(
                club_id=target_club_id,
                include_deleted=True,
            )
        else:
            members = await s.get_members(club_id=target_club_id)

        if not members:
            print("No members found.")
            return

        EXPORT_DIRPATH.mkdir(exist_ok=True)
        csv_filepath = EXPORT_DIRPATH / "club_members.csv"
        fieldnames = list(dict.fromkeys(key for member in members for key in member))

        with csv_filepath.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for m in members:
                writer.writerow(m)

        print(f"Collected {len(members)} members. Written to {csv_filepath}")
    finally:
        await s.clientsession.close()


if __name__ == "__main__":
    asyncio.run(main())
