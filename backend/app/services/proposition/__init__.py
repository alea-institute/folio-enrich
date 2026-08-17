"""Early proposition candidate extraction services."""

from app.services.proposition.extractor import PropositionExtractor
from app.services.proposition.identity import proposition_id

__all__ = ["PropositionExtractor", "proposition_id"]
