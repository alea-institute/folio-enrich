"""Stable identities for proposition spans."""

from uuid import NAMESPACE_URL, uuid5


def proposition_id(
    job_id: object,
    start: int,
    end: int,
    proposition_type: object,
) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"folio-enrich:{job_id}:{start}:{end}:{proposition_type}",
        )
    )
