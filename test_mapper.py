from concept_mapper import ConceptMapper
import unittest

class TestConceptMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = ConceptMapper()

    def test_single_word_lemma(self):
        # "Verantwortlichen" is plural/dative of "Verantwortlicher"
        text = "Den Verantwortlichen obliegt die Pflicht."
        concepts = self.mapper.map_concepts(text)
        self.assertIn("gdpr:Controller", concepts)

    def test_multi_word_lemma(self):
        # "personenbezogenen Daten" is declension of "personenbezogene Daten"
        text = "Die Verarbeitung personenbezogener Daten ist kritisch."
        concepts = self.mapper.map_concepts(text)
        self.assertIn("gdpr:PersonalData", concepts)
        self.assertIn("gdpr:Processing", concepts)

    def test_no_match(self):
        text = "Das Wetter ist heute schön."
        concepts = self.mapper.map_concepts(text)
        self.assertEqual(len(concepts), 0)

    def test_multiple_matches(self):
        text = "Der Auftragsverarbeiter meldet dem Verantwortlichen eine Verletzung des Schutzes."
        concepts = self.mapper.map_concepts(text)
        self.assertIn("gdpr:Processor", concepts)
        self.assertIn("gdpr:Controller", concepts)
        self.assertIn("gdpr:PersonalDataBreach", concepts)

if __name__ == '__main__':
    unittest.main()
