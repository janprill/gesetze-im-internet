from deontic_classifier import DeonticClassifier
import unittest

class TestDeonticClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = DeonticClassifier()

    def test_obligation(self):
        texts = [
            "Der Verantwortliche hat zu gewährleisten, dass...",
            "Der Auftragsverarbeiter muss die Daten löschen.",
            "Sie ist verpflichtet, Auskunft zu geben."
        ]
        for t in texts:
            modality, _ = self.classifier.classify(t)
            self.assertEqual(modality, "Obligation", f"Failed for: {t}")

    def test_prohibition(self):
        texts = [
            "Die Verarbeitung darf nicht ohne Einwilligung erfolgen.",
            "Es ist untersagt, Daten zu übermitteln.",
            "Dies ist verboten."
        ]
        for t in texts:
            modality, _ = self.classifier.classify(t)
            self.assertEqual(modality, "Prohibition", f"Failed for: {t}")

    def test_permission(self):
        texts = [
            "Der Verantwortliche darf Daten verarbeiten.",
            "Die Behörde kann Anordnungen treffen.",
            "Er ist befugt, dies zu tun."
        ]
        for t in texts:
            modality, _ = self.classifier.classify(t)
            self.assertEqual(modality, "Permission", f"Failed for: {t}")

    def test_definition(self):
        texts = [
            "Verantwortlicher ist die natürliche Person...",
            "Dies gilt als Einwilligung."
        ]
        for t in texts:
            modality, _ = self.classifier.classify(t)
            self.assertEqual(modality, "Definition", f"Failed for: {t}")

if __name__ == '__main__':
    unittest.main()
