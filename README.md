# Reeglipõhine NER-parandaja

See kaust sisaldab EstNLTK taggerit, mis parandab olemasolevat NER-märgendust reeglite abil.

Peamine klass on:

- `RuleBasedNerCorrectionTagger`

Sisendiks ootab tagger `Text` objekti, millel on:

- NER-kiht
- morfoloogia kiht
- süntaksi kiht
- `words` kiht

Näide:

```python
from rule_based_ner_correction import RuleBasedNerCorrectionTagger

tagger = RuleBasedNerCorrectionTagger(
    ner_layer="ner",
    morph_layer="morph_analysis",
    syntax_layer="stanza_syntax",
    output_layer="ner_rules_corrected",
)
tagger.tag(text)
```

Parandatud NER-kiht lisatakse samale `Text` objektile tagasi.

Olulisemad failid:

- `boundary/` reeglid, mis parandavad olemasolevate nimeüksuste piire või silte
- `missing/` reeglid, mis lisavad puuduvaid nimeüksusi
- `visualizer/` joonistab süntaksipuu koos soovitavate kihtidega
- `kuidas_reegleid_teha.md` selgitab, kuidas uut reeglit kirjutada
- `testi_reeglit.ipynb` aitab uut reeglit katsetada
- `testimine.py` notebooki abifunktsioonid
