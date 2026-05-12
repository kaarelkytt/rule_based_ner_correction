# Kuidas reegleid teha

Siin paketis on kahte tüüpi reegleid.

- `boundary` reeglid muudavad olemasolevat nimeüksust:
  - laiendavad
  - kahandavad
  - jagavad kaheks
  - eemaldavad
  - muudavad silti
- `missing` reeglid lisavad puuduva nimeüksuse sinna, kus seda enne ei olnud

## Kust alustada

Kõige lihtsam on kasutada notebooki:

- `testi_reeglit.ipynb`

Kirjuta reegel notebooki sisse, lase see 1000 teksti peal läbi ja vaata:

- mitu muudatust tuli
- millised näited välja tulid
- mida `draw_tree` peal näeb

Kui reegel tundub hea, siis tõsta sama klass sobivasse `.py` faili.

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
- kas span peab olema ühesõnaline või mitmesõnaline
- muud odavad kontrollid

### Mida `propose` teeb

`propose` teeb päris otsuse.

Siin:

- kontrollid täpsemaid tingimusi
- ehitad uue span'i
- tagastad `RuleProposal`

Kui reegel ikkagi ei kehti, siis tagasta `None`.

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

Missing-reegli ülemklass on  `BaseMissingRule`:

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
                proposals.append(MissingProposal(self.rule_id, "ORG", i, i + 1, 0.90))
        return proposals
```

`occupied` sisaldab sõnede indekseid, mis on juba mingi nimeüksuse sees.

## Kuhu uus reegel panna

- olemasoleva nimeüksuse muutmine:
  - `boundary/per_rules.py`
  - `boundary/org_rules.py`
  - `boundary/loc_rules.py`
  - `boundary/relable_remove.py`
- puuduva nimeüksuse lisamine:
  - `missing/per_rules.py`
  - `missing/org_rules.py`
  - `missing/loc_rules.py`

Pärast seda lisa reegel registrisse:

- `boundary/registry.py`
- või `missing/registry.py`

## Skoorid

See on reegli tugevuse number. Kui mitu reeglit pakuvad sama span'i jaoks erinevat muudatust, siis suurema skooriga ettepanek jääb peale. Kui skoorid on võrdsed eelistatakse pikemat. Kui ka pikkused on võrdsed, siis võeatakse vasakpoolne nimeüksus.
