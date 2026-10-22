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
    "-l",
    "--list-clubs",
    help="List accessible Spond Clubs (name, id, shortId) and exit",
    action="store_true",
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


async def _resolve_club_id(s: SpondClub, configured_id: str) -> str | None:
    """Resolve `configured_id` (full id, shortId, or name) to the club's full UUID `id`."""
    if (
        configured_id
        and configured_id != "1234567890"
        and len(configured_id) == 32
        and all(c in "0123456789ABCDEFabcdef" for c in configured_id)
    ):
        return configured_id

    clubs = await s.get_clubs()
    if not clubs:
        return None

    for c in clubs:
        if configured_id in (c.get("id"), c.get("shortId"), c.get("name")):
            print(f"Resolved club '{configured_id}' -> {c.get('name')} (id={c['id']})")
            return c["id"]

    fallback = clubs[0]
    print(f"Using discovered club: {fallback.get('name')} (id={fallback['id']})")
    return fallback["id"]


async def main() -> None:
    s = SpondClub(username=username, password=password)
    try:
        if args.list_clubs:
            clubs = await s.get_clubs()
            for c in clubs:
                print(
                    f"Name: {c.get('name')} | id: {c.get('id')} | shortId: {c.get('shortId')}"
                )
            return

        target_club_id = await _resolve_club_id(s, club_id)
        if not target_club_id:
            print("No Spond Clubs found for this account.")
            return

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
