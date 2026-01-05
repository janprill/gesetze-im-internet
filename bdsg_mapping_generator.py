import lxml.etree as ET
from bs4 import BeautifulSoup
import re
from concept_mapper import ConceptMapper
from deontic_classifier import DeonticClassifier

class BDSGMappingGenerator:
    def __init__(self, input_file, output_file):
        self.input_file = input_file
        self.output_file = output_file
        self.mapper = ConceptMapper()
        self.classifier = DeonticClassifier()

        # Namespaces from rioKB_GDPR.xml
        self.NSMAP = {
            "lrml": "http://docs.oasis-open.org/legalruleml/ns/v1.0/",
            "ruleml": "http://ruleml.org/spec",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xs": "http://www.w3.org/2001/XMLSchema",
            # Prefixes used in content
            "gdpr": "/akn/eu/act/regulation/2018-05-25/eng@2018-05-25/!main#",
            "prOnto": "https://w3id.org/ontology/pronto#",
            "dapreco": "http://www.liviorobaldo.com/dapreco#",
            "rioOnto": "http://www.liviorobaldo.com/rioOnto#"
        }

    def run(self):
        print(f"Reading {self.input_file}...")
        with open(self.input_file, "r", encoding="utf-8") as f:
            xml_content = f.read()

        # Parse BDSG XML using BeautifulSoup (easier for text extraction from arbitrary XML structures)
        # Note: The provided BDSG XML seems to use tags like <norm>, <metadaten>, <textdaten>, <Content>, <P>
        soup = BeautifulSoup(xml_content, "xml")

        # Build Output XML
        lrml = self.NSMAP["lrml"]
        root = ET.Element(f"{{{lrml}}}LegalRuleML", nsmap=self.NSMAP)

        # Add Prefix definitions
        self._add_prefix(root, "gdpr", self.NSMAP["gdpr"])
        self._add_prefix(root, "prOnto", self.NSMAP["prOnto"])
        self._add_prefix(root, "dapreco", self.NSMAP["dapreco"])
        # Add a prefix for BDSG itself? Not strictly defined in prompt, but useful.
        self._add_prefix(root, "BDSG", "http://www.gesetze-im-internet.de/bdsg_2018/")

        # Iterate norms (paragraphs)
        norms = soup.find_all("norm")
        print(f"Found {len(norms)} norms.")

        for norm in norms:
            self._process_norm(norm, root)

        # Write to file
        tree = ET.ElementTree(root)
        print(f"Writing to {self.output_file}...")
        tree.write(self.output_file, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    def _add_prefix(self, parent, prefix, refID):
        lrml = self.NSMAP["lrml"]
        elem = ET.SubElement(parent, f"{{{lrml}}}Prefix")
        elem.set("pre", prefix)
        elem.set("refID", refID)

    def _process_norm(self, norm, root):
        # Extract ID/Title
        metadaten = norm.find("metadaten")
        enbez = metadaten.find("enbez").text if metadaten and metadaten.find("enbez") else "Unknown"
        titel = metadaten.find("titel").text if metadaten and metadaten.find("titel") else ""

        # Extract Content Paragraphs
        textdaten = norm.find("textdaten")
        if not textdaten:
            return

        content_block = textdaten.find("Content")
        if not content_block:
            return

        paragraphs = content_block.find_all("P")

        ruleml = self.NSMAP["ruleml"]
        lrml = self.NSMAP["lrml"]

        for i, p in enumerate(paragraphs):
            text = p.get_text().strip()
            if not text:
                continue

            # 1. Classify
            modality, lrml_class = self.classifier.classify(text)

            # 2. Map Concepts
            concepts = self.mapper.map_concepts(text)

            if not concepts:
                continue # Skip rules with no relevant entities? Or keep them?
                         # Prompt says "attempting to map not just high-level entities but specific legal concepts".
                         # If no concepts found, the rule might be irrelevant to the bridge. We skip for noise reduction.

            # Create Rule Wrapper (Statement)
            # Structure: <lrml:PrescriptiveStatement> or <lrml:ConstitutiveStatement>
            # Inside: <ruleml:Rule> ...

            # Note: The mapping structure in rioKB is complex. We simplify based on "Pipeline Logic":
            # "Create a <ruleml:Rule> for the paragraph."

            statement = ET.SubElement(root, f"{{{lrml}}}{modality}Statement" if modality != "Definition" else f"{{{lrml}}}ConstitutiveStatement")
            # Ref to source
            statement.set("key", f"BDSG_{enbez}_{i+1}".replace(" ", "_").replace("§", "Para"))

            rule = ET.SubElement(statement, f"{{{ruleml}}}Rule")
            # Logic: If Exists(Entities) Then Modality(Entities)
            # Ideally we construct a proper logic formula.
            # <ruleml:if> ... </ruleml:if>
            # <ruleml:then> ... </ruleml:then>

            if_block = ET.SubElement(rule, f"{{{ruleml}}}if")
            then_block = ET.SubElement(rule, f"{{{ruleml}}}then")

            # IF Block: Existential quantification of found concepts
            # For simplicity: And(Atom(Concept(x)), ...)
            if len(concepts) > 1:
                logic_op = ET.SubElement(if_block, f"{{{ruleml}}}And")
            else:
                logic_op = if_block

            for concept in concepts:
                # Atom: Concept(x)
                atom = ET.SubElement(logic_op, f"{{{ruleml}}}Atom")
                op = ET.SubElement(atom, f"{{{ruleml}}}Op")
                rel = ET.SubElement(op, f"{{{ruleml}}}Rel")
                # concept is like "gdpr:Controller". We need to split prefix if using namespaces in XML attributes,
                # or just put it as IRI. RuleML often uses IRIs.
                rel.set("iri", concept)

                # Variable or generic instance?
                # Using a generic variable ?x for the entity
                var = ET.SubElement(atom, f"{{{ruleml}}}Var")
                var.text = "x" # Simplified. In real world, different concepts might be different variables.

            # THEN Block: The modality applies to these entities.
            # This is "Deontic Logic".
            # Usually <lrml:Obligation> ... </lrml:Obligation> wraps the rule in LegalRuleML,
            # OR the rule conclusion implies the obligation.
            # The prompt says: "In the <ruleml:then> block, apply the deontic logic (e.g., 'The Controller is Obligated to do X')"
            # However, LegalRuleML separates the Deontic operator from the Rule usually.
            # But adhering to the prompt:
            # "In the <ruleml:then> block, apply the deontic logic"

            # We will represent the Deontic modality as a predicate in the conclusion for this mapping file.
            # E.g. OBLIGATED(x)

            deontic_atom = ET.SubElement(then_block, f"{{{ruleml}}}Atom")
            deontic_op = ET.SubElement(deontic_atom, f"{{{ruleml}}}Op")
            deontic_rel = ET.SubElement(deontic_op, f"{{{ruleml}}}Rel")
            deontic_rel.set("iri", f"dapreco:{modality.upper()}") # e.g. dapreco:OBLIGATION

            # Apply to the variables found
            var = ET.SubElement(deontic_atom, f"{{{ruleml}}}Var")
            var.text = "x"

if __name__ == "__main__":
    generator = BDSGMappingGenerator(
        "data/items/bdsg_2018/BJNR209710017.xml",
        "rioKB_Mapping_BDSG.xml"
    )
    generator.run()
