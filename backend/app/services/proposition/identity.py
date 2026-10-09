"""Stable identities for proposition spans.

Two identities coexist:

* ``proposition_id`` (this module) is the job-scoped legacy id: a uuid5 over
  ``(job id, start, end, proposition type)``. It stays the ``Proposition.id``
  because gold annotation sessions key candidates on it. The same text
  submitted in two jobs gets two different ids.
* ``content_iri`` (``Proposition.content_iri``, minted by
  :mod:`app.services.proposition.source`) is the cross-document identity
  shared with folio-insights: ``urn:folio:shard/<hex>`` over the normalized
  ``(source URI, span text)``. It is the same in every job over the same
  source and matches the folio-insights shard IRI for that span.
"""

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
