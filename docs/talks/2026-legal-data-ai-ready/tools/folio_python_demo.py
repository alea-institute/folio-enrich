"""FOLIO in a few lines: load the ontology, search, read translations and parents."""
import time
from folio import FOLIO

t0 = time.time()
folio = FOLIO()  # pulls the OWL file from github.com/alea-institute/FOLIO and parses it
print(f"Loaded {len(folio.classes):,} concepts in {time.time() - t0:.1f}s")

concept, score = folio.search_by_label("arbitration", limit=1)[0]
print(concept.label, "|", concept.iri, f"| score {score:.0f}")
print("es:", concept.translations.get("es-es"), "| pt:", concept.translations.get("pt-br"))
print("parents:", [folio[p].label for p in concept.sub_class_of])
