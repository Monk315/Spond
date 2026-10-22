"""Client for the Spond Club administration and finance API.

Spond Club is the administration tier sold to clubs/teams alongside the free
consumer app. It exposes a separate API (`api.spond.com/club/v1/`) for club
management (clubs, members) and finance-flavoured data such as
transactions/payments. Use the `SpondClub` class for this API and
`spond.spond.Spond` for everything else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from .base import _SpondBase

if TYPE_CHECKING:
    from . import JSONDict


class SpondClub(_SpondBase):
    """Async client for the Spond Club API (`https://api.spond.com/club/v1/`).

    Authentication uses the same email/password credentials as the consumer
    API, authenticating against `https://api.spond.com/club/v1/login`. The user
    must belong to at least one Spond Club organisation and the `club_id`
    passed to club-scoped methods must be one they have access to. The
    `club_id` here is distinct from the consumer-API `groupId` (you can
    discover accessible clubs with `get_clubs()`).

    Example
    -------
    ```python
    import asyncio
    from spond import club

    async def main():
        sc = club.SpondClub(username="me@example.invalid", password="secret")
        members = await sc.get_members(club_id="ABCD1234...")
        for m in members:
            print(m.get("firstName"), m.get("lastName"))
        await sc.clientsession.close()

    asyncio.run(main())
    ```
    """

    _API_BASE_URL: ClassVar = "https://api.spond.com/club/v1/"
    _LOGIN_ENDPOINT: ClassVar = "login"

    def __init__(self, username: str, password: str) -> None:
        """Construct a Spond Club client.

        Parameters
        ----------
        username : str
            Spond account email. Same credentials as the consumer API; the
            account must have access to at least one Spond Club organisation
            for the API calls to return data.
        password : str
            Spond account password.
        """
        super().__init__(username, password, self._API_BASE_URL)
        self.clubs: list[JSONDict] | None = None
        self.members: list[JSONDict] | None = None
        self.transactions: list[JSONDict] | None = None

    def _club_headers(self, club_id: str) -> dict[str, str]:
        """Return authenticated request headers scoped to `club_id`."""
        return {**self.auth_headers, "X-Spond-Clubid": club_id}

    @_SpondBase.require_authentication
    async def get_clubs(self) -> list[JSONDict]:
        """Retrieve all Spond Clubs accessible to the authenticated user.

        Useful for discovering the `id` (`club_id`) and `shortId` of clubs
        the account can administer without copying the ID from the web UI.
        The response is cached on `self.clubs`.

        Returns
        -------
        list[JSONDict]
            A list of club dicts (each typically containing `id`, `shortId`,
            `name`, `permissions`, etc.).

        Raises
        ------
        ValueError
            Raised when the request to the API fails.
        """
        url = f"{self.api_url}clubs"
        async with self.clientsession.get(url, headers=self.auth_headers) as r:
            if not r.ok:
                error_details = await r.text()
                raise ValueError(
                    f"Request failed with status {r.status}: {error_details}"
                )
            self.clubs = await r.json()
            return self.clubs

    @_SpondBase.require_authentication
    async def get_members(
        self,
        club_id: str,
        *,
        include_processed: bool | None = None,
        include_unprocessed: bool | None = None,
        include_deleted: bool | None = None,
    ) -> list[JSONDict]:
        """Retrieve members for a Spond Club from `club/v1/members`.

        By default (when no filter flags are passed), requests
        `GET https://api.spond.com/club/v1/members` with the `X-Spond-Clubid`
        header, matching the default active-members query used by the
        `club.spond.com` web interface (`https://api.spond.com/club/v1/members?`).
        Optional boolean flags allow filtering for unprocessed or deactivated
        members.

        The response is cached on `self.members`.

        Parameters
        ----------
        club_id : str
            Identifier for the club (`X-Spond-Clubid` header). Distinct from
            the consumer API's `groupId`.
        include_processed : bool, optional
            If specified, passes `includeProcessed` (`"true"`/`"false"`) as a
            query parameter.
        include_unprocessed : bool, optional
            If specified, passes `includeUnprocessed` (`"true"`/`"false"`) as a
            query parameter (e.g. `include_processed=False,
            include_unprocessed=True, include_deleted=False` for pending
            members).
        include_deleted : bool, optional
            If specified, passes `includeDeleted` (`"true"`/`"false"`) as a
            query parameter.

        Returns
        -------
        list[JSONDict]
            A list of member dictionaries for the club. Each member dict
            typically includes `id`, `firstName`, `lastName`, `profile`,
            `guardians`, `fieldValues`, `joinedDate`, `type`, `address`, etc.

        Raises
        ------
        ValueError
            Raised when the request to the API fails (non-2xx status).
        """
        url = f"{self.api_url}members"
        params: dict[str, str] = {}
        if include_processed is not None:
            params["includeProcessed"] = str(include_processed).lower()
        if include_unprocessed is not None:
            params["includeUnprocessed"] = str(include_unprocessed).lower()
        if include_deleted is not None:
            params["includeDeleted"] = str(include_deleted).lower()

        async with self.clientsession.get(
            url,
            headers=self._club_headers(club_id),
            params=params or None,
        ) as r:
            if not r.ok:
                error_details = await r.text()
                raise ValueError(
                    f"Request failed with status {r.status}: {error_details}"
                )
            self.members = await r.json()
            return self.members

    @_SpondBase.require_authentication
    async def get_member(self, club_id: str, member_id: str) -> JSONDict:
        """Retrieve a single member by ID from `club/v1/members/{member_id}`.

        Parameters
        ----------
        club_id : str
            Identifier for the club (`X-Spond-Clubid` header).
        member_id : str
            Unique identifier of the club member.

        Returns
        -------
        JSONDict
            The member dictionary as returned by the Spond Club API.

        Raises
        ------
        KeyError
            If `member_id` is blank or no member with that ID exists (HTTP 404).
        ValueError
            If the API returns any other error status.
        """
        if not member_id:
            raise KeyError(f"No member with id='{member_id}'.")
        url = f"{self.api_url}members/{member_id}"
        async with self.clientsession.get(
            url, headers=self._club_headers(club_id)
        ) as r:
            if r.status == 404:
                raise KeyError(f"No member with id='{member_id}'.")
            if not r.ok:
                error_details = await r.text()
                raise ValueError(
                    f"Request failed with status {r.status}: {error_details}"
                )
            return await r.json()

    @_SpondBase.require_authentication
    async def get_transactions(
        self, club_id: str, skip: int | None = None, max_items: int = 100
    ) -> list[JSONDict]:
        """Retrieve transactions/payments for a Spond Club.

        Spond's transactions endpoint returns at most 25 records per request,
        so this method paginates internally (via recursion on `skip`) until
        either `max_items` is reached or the server returns an empty page.

        **Caching caveat**: results accumulate on `self.transactions` and
        the cache is **not** keyed by `club_id` — calling this method again
        with a different `club_id` on the same instance will append that
        club's transactions to the same list, mixing the two. If you query
        multiple clubs from one client, reset the cache between calls
        (`sc.transactions = None`) or use a fresh `SpondClub` instance per
        club.

        Each transaction dict typically includes at least `id`, `paidAt`,
        `paymentName`, and `paidByName`. See `examples/transactions.py` for
        a usage example.

        Parameters
        ----------
        club_id : str
            Identifier for the club. Note that this is **different** from the
            `groupId` used elsewhere in the Spond API — find it in the URL
            of the Spond Club web UI.
        skip : int, optional
            Pagination cursor (number of records to skip). Normally left as
            `None`; the method increments it itself on recursive calls. Only
            override if you know what you're doing.
        max_items : int, optional
            Stop fetching once at least this many transactions are
            accumulated. Defaults to 100. The final list may be slightly
            longer than `max_items` since the server returns pages of 25.

        Returns
        -------
        list[JSONDict]
            All transactions accumulated so far (across recursive page
            fetches). Empty list if the club has no transactions.
        """
        if self.transactions is None:
            self.transactions = []

        url = f"{self.api_url}transactions"
        params = None if skip is None else {"skip": skip}
        headers = self._club_headers(club_id)

        async with self.clientsession.get(url, headers=headers, params=params) as r:
            if r.status == 200:
                t = await r.json()
                if len(t) == 0:
                    return self.transactions

                self.transactions.extend(t)
                if len(self.transactions) < max_items:
                    return await self.get_transactions(
                        club_id=club_id,
                        skip=len(t) if skip is None else skip + len(t),
                        max_items=max_items,
                    )

        return self.transactions
