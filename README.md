# Reeglipõhine NER-parandaja

See kaust sisaldab EstNLTK taggerit, mis parandab olemasolevat NER-märgendust reeglite abil.

Peamine klass on:

- `RuleBasedNerCorrectionTagger`

Tagger eeldab `Text` objekti, millel on olemas:

- NER-kiht
- morfoloogiakiht
- süntaksikiht
- `words` kiht

## Lihtne kasutus

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

Parandatud NER-kiht lisatakse samale `Text` objektile.

## Reeglite etteandmine

Taggerile võib anda kõik reeglid ühe listina:

```python
from rule_based_ner_correction import RuleBasedNerCorrectionTagger, get_default_rules

rules = get_default_rules()
tagger = RuleBasedNerCorrectionTagger(rules=rules)
```

Tagger jagab reeglid ise faaside järgi nelja rühma:

- `split`
- `adjust`
- `finalize`
- `missing`

Kui reegleid ette ei anta, kasutatakse sama vaikimisi komplekti automaatselt.

## Tööjärjekord

Parandused tehakse neljas etapis:

1. `split` – vigase span’i jagamine
2. `adjust` – span’i laiendamine või kärpimine
3. `finalize` – viimased ümbermärgistused ja eemaldused
4. `missing` – puuduva nimeüksuse lisamine

## Olulisemad failid

- `boundary/` – olemasolevaid nimeüksusi muutvad reeglid
- `missing/` – puuduvaid nimeüksusi lisavad reeglid
- `registry.py` – vaikimisi reeglid ja reeglite jaotus faaside järgi
- `visualizer/` – süntaksipuu joonistamine koos valitud kihtidega
- `kuidas_reegleid_teha.md` – lühike juhend uue reegli kirjutamiseks
- `testi_reeglit.ipynb` – ühe reegli eraldi katsetamine
- `reegli_testimine.py` – notebooki abifunktsioonid
