class DeonticClassifier:
    def __init__(self):
        # Keywords for classification
        self.obligation_keywords = ["hat zu", "muss", "ist verpflichtet", "sind verpflichtet", "haben zu"]
        self.prohibition_keywords = ["darf nicht", "ist untersagt", "verboten", "nicht gestattet"]
        self.permission_keywords = ["darf", "kann", "ist befugt", "können"]
        self.definition_keywords = ["ist", "gilt als", "bedeutet", "sind"]

    def classify(self, text):
        """
        Classifies the text into a Deontic modality.
        Returns a tuple: (ClassificationType, RuleML_Class)

        ClassificationType: Obligation, Prohibition, Permission, Definition
        """
        text_lower = text.lower()

        # Priority: Prohibition > Obligation > Permission > Definition (heuristic)

        # Check Prohibition
        for kw in self.prohibition_keywords:
            if kw in text_lower:
                return "Prohibition", "lrml:Prohibition"

        # Check Obligation
        for kw in self.obligation_keywords:
            if kw in text_lower:
                return "Obligation", "lrml:Obligation"

        # Check Permission
        for kw in self.permission_keywords:
            if kw in text_lower:
                return "Permission", "lrml:Permission"

        # Check Definition (Constitutive)
        # Definitions are tricky because "ist" is very common.
        # We might need stricter rules or just default to Constitutive if it looks like a definition.
        # For now, we use the keyword list but apply it carefully.
        for kw in self.definition_keywords:
            # Simple check: if it starts with "X ist..." or contains "gilt als"
            if kw in text_lower:
                 return "Definition", "lrml:ConstitutiveStatement"

        # Default fallback if no specific modality found, usually treated as Constitutive or just a Statement
        return "Statement", "lrml:ConstitutiveStatement"
