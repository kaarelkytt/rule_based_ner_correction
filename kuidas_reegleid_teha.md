# Kuidas reegleid teha

Siin paketis on kahte tüüpi reegleid.

- `boundary` reeglid muudavad olemasolevat nimeüksust:
  - jagavad kaheks
  - laiendavad
  - kahandavad
  - eemaldavad
  - muudavad silti
- `missing` reeglid lisavad puuduva nimeüksuse sinna, kus seda enne ei olnud

## Kust alustada

Kõige lihtsam on kasutada notebooki:

- `testi_reeglit.ipynb`

Kirjuta reegel notebooki sisse, lase see valitud teksti hulga peal läbi ja vaata:

- mitu muudatust tuli
- millised näited välja tulid
- mida `draw_tree` peal näeb

Kui reegel tundub hea, tõsta sama klass sobivasse `.py` faili.

## Boundary-reegel

Boundary-reegli ülemklass on `BaseRule`:

```python
from rule_based_ner_correction.boundary.base import BaseRule, RuleProposal


class MinuReegel(BaseRule):
    rule_id = "minu_reegel"
    description = "Lühike selgitus, mida reegel teeb."

    def applies_to(self, span, context):
        return span.label == "ORG"

    def propose(self, span, context):
        next_token = context.next_token(span)
        if next_token is None:
            return None

        new_span = context.span_from_indices(span.label, span.start_i, span.end_i + 1)
        return RuleProposal(
            rule_id=self.rule_id,
            operation="replace",
            score=0.95,
            spans=[new_span],
        )
```

### Mida `applies_to` teeb

`applies_to` on kiire eelfilter.

Siia pane:

- millise sildi kohta reegel käib
- kas span peab olema ühe- või mitmesõnaline
- muud lihtsad kontrollid

### Mida `propose` teeb

`propose` teeb päris otsuse.

Siin:

- kontrollid täpsemaid tingimusi
- ehitad uue span'i
- tagastad `RuleProposal`

Kui reegel ikkagi ei kehti, tagasta `None`.

### Boundary-reegli faasid

Boundary-reeglitel saab olla faas:

- `split` - esmalt jagatakse vigased span'id väiksemaks
- `adjust` - seejärel laiendatakse või kärbitakse
- `finalize` - lõpus tehakse eemaldused ja ümbermärgendused

Vaikimisi on `stage = "adjust"`. Kui tahad, et reegel jookseks enne teisi, lisa klassile näiteks:

```python
stage = "split"
```

### Boundary-reegli operatsioonid

Kõige tavalisem on:

- `operation="replace"` ja `spans=[new_span]`

Jagamiseks:

- `operation="split"` ja `spans=[left_span, right_span]`

Eemaldamiseks:

- `operation="remove"` ja `spans=[]`

Sildi muutmiseks tee lihtsalt uus span uue sildiga:

```python
new_span = context.span_from_indices("PER", span.start_i, span.end_i)
```

## Missing-reegel

Missing-reegli ülemklass on `BaseMissingRule`:

```python
from rule_based_ner_correction.missing.base import BaseMissingRule, MissingProposal


class MinuPuuduvaReegel(BaseMissingRule):
    rule_id = "minu_puuduva_reegel"
    description = "Lisab puuduva ORG märgendi."

    def find(self, context, occupied):
        proposals = []
        for i, token in enumerate(context.tokens):
            if i in occupied:
                continue
            if token.text == "ETV":
                proposals.append(
                    MissingProposal(self.rule_id, "ORG", i, i + 1, 0.90)
                )
        return proposals
```

`occupied` sisaldab sõnede indekseid, mis on juba mingi nimeüksuse sees.

## Kuhu uus reegel panna

- olemasoleva nimeüksuse muutmine:
  - `boundary/split_rules.py`
  - `boundary/adjust_rules.py`
  - `boundary/finalize_rules.py`
- puuduva nimeüksuse lisamine:
  - `missing/per_rules.py`
  - `missing/org_rules.py`
  - `missing/loc_rules.py`

Pärast seda lisa reegel registrisse:

- `boundary/registry.py`
- või `missing/registry.py`

Taggerile saab anda kõik reeglid ühe listina. Sel juhul jagab tagger need ise `stage` välja järgi õigetesse faasidesse:

```python
from rule_based_ner_correction import RuleBasedNerCorrectionTagger, get_default_rules

rules = get_default_rules() + [MinuReegel()]
tagger = RuleBasedNerCorrectionTagger(rules=rules)
```

## Skoorid

Skoor näitab, milline ettepanek võidab, kui mitu reeglit pakuvad sama koha jaoks erinevat muudatust.

- suurem skoor võidab
- võrdse skoori korral eelistatakse pikemat tulemust
- kui ka pikkus on sama, eelistatakse vasakpoolsemat tulemust
