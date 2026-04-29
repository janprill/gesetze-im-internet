from sgbpot.span_ids import normalize_paragraph_id, norm_id, paragraph_span_id, sentence_span_id


def test_normalize_paragraph_variants():
    assert normalize_paragraph_id("§ 24") == "§24"
    assert normalize_paragraph_id("§ 24a") == "§24a"
    assert normalize_paragraph_id("Art. 1") == "Art.1"


def test_norm_id_and_sentence_span_id():
    assert norm_id("SGB_X", "§ 24") == "SGB_X:§24"
    assert paragraph_span_id("SGB_X:§24", 1) == "SGB_X:§24:Abs1"
    assert sentence_span_id("SGB_X:§24", 1, 2) == "SGB_X:§24:Abs1:S2"
