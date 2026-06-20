# Street Cleaning - Project README

## 1. Qellimi i projektit
Ky projekt zgjidh problemin e planifikimit te rrugeve per automjetet e pastrimit ne nje qytet te modeluar si graf.

Objektivi eshte:
- te pastrohen patjeter te gjitha rruget Mandatory,
- te pastrohen sa me shume rruge Optional,
- te minimizohet humbja e ujit,
- dhe cdo automjet te nise/perfundoje ne depot brenda kohes T.

Score-i i problemit eshte:

`Score = alpha * Coverage + (1 - alpha) * Efficiency`

ku Coverage rritet me gjatesine e rrugeve te pastruara, ndersa Efficiency rritet kur humbja e ujit eshte e vogel.

## 2. Si e kemi zgjedhur problemin (qasja)
Problemi eshte kombinim i:
- route planning ne graf me drejtime,
- asignim detyrash me kufizime kapaciteti,
- dhe optimizim multi-objektiv.

Per shkak te madhesise se instancave, kemi perdorur qasje heuristike (jo exact solver), e cila jep zgjidhje valide dhe praktikisht te mira ne kohe te shpejte.

Qasja jone ndahet ne 3 faza:
1. Mandatory-first planning (prioritet absolut validiteti).
2. Mandatory repair (rikuperim nese ngelin rrugica te detyrueshme).
3. Optional optimization (permiresim score pasi validiteti sigurohet).

## 3. Algoritmi ne solver.py
Implementimi kryesor eshte ne `solver.py`.

### 3.1 Modelimi i grafit
- Cdo rruge ruhet me: nyje A/B, drejtim, kohe traversimi, gjatesi, kategori, kerkese uji.
- Ndertohet graf i orientuar sipas `direction`.
- Përdoret Dijkstra per rrugen me te shkurter nga pika aktuale e automjetit.

### 3.2 Planifikimi i Mandatory
Per secilin automjet mbahet gjendja:
- pozicioni aktual,
- koha e perdorur,
- rruga e ndertuar,
- edge-id qe pastron.

Strategjia:
- kategorite Mandatory ndahen sipas kerkeses (`req=10/20/30`),
- provohen disa variante renditjeje automjetesh dhe policy-t,
- zgjidhet varianti me me pak Mandatory te pambuluara.

Kjo faze favorizon automjetin me kapacitetin minimal te mjaftueshem per te ulur waste.

### 3.3 Mandatory repair dhe lookahead
Nese pas planit fillestar ngelin Mandatory:
- provohet repair me round-trips nga depot,
- provohet insertion/rewiring per te futur edge te munguar,
- perdoret lookahead repair: simulohet ndryshimi i segmentit, vleresohet sa Mandatory mbesin dhe merret kandidati me i mire.

Qellimi i kesaj faze eshte te minimizoje (ideal 0) numrin e Mandatory te munguar pa perdorur hardcode per instanca te vecanta.

### 3.4 Optional optimization
Pasi Mandatory jane trajtuar:
- automjetet me kapacitet me te vogel perdoren te parat per Optional,
- vendimi per pastrim bazohet ne gain te objektivit (`coverage - waste` i peshuar me alpha),
- behet edhe enrichment ne edge Optional te traversuara kur fitimi i objektivit eshte pozitiv.

### 3.5 Output dhe validimi
`solver.py` gjeneron file ne formatin e kerkuar nga platforma:
- per cdo automjet: numri i edge-ve te traversuara (`nodes - 1`),
- lista e nyjeve te rruges,
- lista e edge-id te pastruara.

Pastaj output-i validohet lokalisht nga kontrollet e integruara.

## 4. Si i kemi perdorur kerkesat e problemit
Kerkesat kryesore dhe si zbatohen:

1. Te gjitha Mandatory duhet te pastrohen:
- enforce ne fazen Mandatory-first,
- plus repair dhe lookahead nese mbeten edge te detyrueshme.

2. Respektim i drejtimit te rrugeve:
- graf i orientuar dhe traversim vetem ne edge valide.

3. Kufiri kohor per automjet:
- cdo kandidat pranohet vetem nese rruga mbetet `<= T` me kthim ne depot.

4. Kufizimi i kapacitetit te pastrimit:
- edge pastrohet vetem kur `vehicle_capacity >= edge_req`.

5. Fillim/fund ne depot:
- te gjitha rruget mbyllen ne depot para shkrimit te output-it.

6. Objektivi Coverage/Efficiency:
- Optional zgjidhen me funksion vlere te varur nga `alpha`,
- waste penalizohet sipas diferences `capacity - req`.

## 5. Pse kjo qasje
Arsyet kryesore:
- instancat jane te medha per optimizim exact ne kohe te arsyeshme,
- validiteti (Mandatory + kufizime) eshte prioritet absolut,
- heuristikat multi-variant + repair japin kompromis te mire mes cilesise dhe shpejtesise.

## 6. Struktura e projektit
- `solver.py` - zgjidhja kryesore.
- `check_submission.py` - validim formati i output-it.
- `normalize_submission.py` - normalizim i fushes se route-count kur duhet.
- `inputs/` - instancat hyrëse.
- `outputs/` - file-t e gjeneruar nga solver.
- `submissions/` - variante eksperimenti historike (opsionale).

## 7. Si ekzekutohet
Nga root i projektit:

```bash
python solver.py --input inputs/train_a.txt --output outputs/train_a_output.txt
python solver.py --input inputs/train_b.txt --output outputs/train_b_output.txt
python solver.py --input inputs/train_n.txt --output outputs/train_n_output.txt
python solver.py --input inputs/m.txt --output outputs/m_output.txt
```

Kontroll formati:

```bash
python check_submission.py --file outputs/train_a_output.txt
python check_submission.py --file outputs/train_b_output.txt
python check_submission.py --file outputs/train_n_output.txt
python check_submission.py --file outputs/m_output.txt
```

## 8. Shenime
- Solver-i eshte heuristik dhe general per instanca te ketij formati (jo i hardcoduar per emra instancash specifike).
- Si cdo heuristike, nuk garanton optimalitet global ne cdo rast, por synon validitet robust dhe score te mire praktik.
