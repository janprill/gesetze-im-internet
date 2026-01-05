import spacy

class ConceptMapper:
    def __init__(self, model="de_core_news_sm"):
        try:
            self.nlp = spacy.load(model)
        except OSError:
            print(f"Warning: Model '{model}' not found. Downloading...")
            from spacy.cli import download
            download(model)
            self.nlp = spacy.load(model)

        self.mapping_dict = {
            # Actors
            "Verantwortlicher": "gdpr:Controller",
            "Auftragsverarbeiter": "gdpr:Processor",
            "Empfänger": "gdpr:Recipient",
            "Dritter": "gdpr:ThirdParty",
            "Vertreter": "gdpr:Representative",
            "Aufsichtsbehörde": "gdpr:SupervisoryAuthority",

            # Data Objects
            "personenbezogene Daten": "gdpr:PersonalData",
            "genetische Daten": "gdpr:GeneticData",
            "biometrische Daten": "gdpr:BiometricData",
            "Gesundheitsdaten": "gdpr:DataConcerningHealth",
            "Dateisystem": "gdpr:FilingSystem",

            # Actions/Processes
            "Verarbeitung": "gdpr:Processing",
            "Profiling": "gdpr:Profiling",
            "Pseudonymisierung": "gdpr:Pseudonymisation",
            "Einwilligung": "gdpr:Consent",
            "Verletzung des Schutzes": "gdpr:PersonalDataBreach",
        }

        # Extended synonyms/lemmas map for tricky German terms
        self.synonyms = {
            "verantwortliche": "Verantwortlicher",
            "verantwortlicher": "Verantwortlicher",
            "verantwortlichen": "Verantwortlicher",
            "auftragsverarbeiters": "Auftragsverarbeiter",
        }

        # Split into single and multi-word
        self.multi_word_terms = {k: v for k, v in self.mapping_dict.items() if " " in k}
        self.single_word_terms = {k: v for k, v in self.mapping_dict.items() if " " not in k}

    def map_concepts(self, text):
        """
        Analyzes the text and returns a list of mapped concepts (Ontology Classes).
        """
        doc = self.nlp(text)
        found_concepts = set()

        # 1. Check for single word terms
        for token in doc:
            lemma = token.lemma_.lower()
            text_lower = token.text.lower()

            # Check exact mapping keys (normalized)
            for term, concept in self.single_word_terms.items():
                if term.lower() == lemma or term.lower() == text_lower:
                    found_concepts.add(concept)

            # Check synonyms
            if lemma in self.synonyms:
                normalized_term = self.synonyms[lemma]
                if normalized_term in self.single_word_terms:
                    found_concepts.add(self.single_word_terms[normalized_term])

            # Fallback check for "Verantwortlich..." starts
            if lemma.startswith("verantwortlich") and "gdpr:Controller" not in found_concepts:
                 # Heuristic: if it's a noun (mostly), but Spacy might tag it as ADJ.
                 # Let's check strict start matching for this specific critical term if we haven't found it.
                 pass

        # 2. Check for multi-word phrases
        # We normalize the doc to a string of lemmas for searching
        doc_lemmas = " ".join([t.lemma_.lower() for t in doc])
        doc_text_lower = text.lower()

        for term, concept in self.multi_word_terms.items():
            # Lemmatize the search term
            term_doc = self.nlp(term)
            term_lemmas = " ".join([t.lemma_.lower() for t in term_doc])

            if term_lemmas in doc_lemmas:
                found_concepts.add(concept)
            elif term.lower() in doc_text_lower:
                found_concepts.add(concept)

        return list(found_concepts)
