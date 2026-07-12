"""One-off: parse the IMOS CurrentOrganization export into CCSM_MISSION_ORG_ROWS
JS literal, printed to stdout for pasting into CcsmData.gs. No data leaves the machine.

Deviations from the original sketch (see task-2-brief.md), discovered by
inspecting the real export:
  - The export includes a 'Service' zone (a service missionary not tied to
    any of the 10 CCSM teaching zones/areas) and blank spacer rows between
    every record. Both are dropped.
  - Area/Zone/District values are stripped and then mapped onto the
    canonical CCSM_ZONES strings (verbatim from WeeklyReportForm.gs) so the
    emitted Area_Name is guaranteed to be codepoint-identical to CCSM_ZONES,
    not just str-equal after stripping.
  - A few areas have MORE than 3 missionaries assigned (two saw 4, one saw
    5 — likely AP/leadership housing overlap or transfer-cycle overlap, not
    literal trios). The brief anticipated only trios (append 3rd name to
    Companion2_Name with ' / '); this generalizes that rule to N names:
    Companion1_Name = first name, Companion2_Name = every remaining name
    joined with ' / ', so nobody in the export is silently dropped.
"""
import pandas as pd, json, sys

# Windows terminals often default stdout/stderr to cp1252, which mangles the
# Spanish accented characters (ñ, á, í, etc.) in this data — force UTF-8.
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

SRC = r"C:\Users\2011794-MTS\Downloads\CurrentOrganization-Excel (3).xls"

# Canonical zones/areas — copied verbatim from WeeklyReportForm.gs (CCSM_ZONES).
ZONES = {
  'San Pedro': ['Boca de la Costa 1', 'Boca de la Costa 2', 'Bosque Mar 1', 'Bosque Mar 2', 'La Marina 1', 'Lomas Coloradas 1', 'Lomas Coloradas 2', 'Los Huertos', 'Oficina 1', 'San Pedro', 'San Pedro 2', 'Santa Juana'],
  'Camilo': ['Camilo Olivarria 1', 'Camilo Olivarria 2', 'Camilo Olivarria 3', 'Coronel', 'Lagunillas 1', 'Lagunillas 2', 'Lota 1', 'Lota 2'],
  'Arauco': ['Arauco 1', 'Arauco 2', 'Cañete 1', 'Cañete 2', 'Curanilahue 1', 'Curanilahue 2', 'Lebu 1', 'Lebu 2', 'Los Alamos'],
  'Los Angeles Norte': ['Almirante Latorre', 'Cabrero 1', 'Cabrero 2', 'Galvarino', 'Galvarino 2', 'Huepil & Tucapel & Villa Obispo', 'Laja 1', 'Laja 2', "Villa O'Higgins", 'Villa Obispo', 'Yumbel'],
  'Los Angeles Sur': ['Av. Alemania', 'Mulchen 1', 'Mulchen 2', 'Nacimiento 1', 'Nacimiento 2', 'San Martin 2', 'San Martín 1', 'Santa Barbara', 'Villa Esmeralda', 'Villa Las Americas 1', 'Villa las Americas 2'],
  'Angol': ['Alemania 1', 'Alemania 2', 'Collipulli', 'El Mirador', 'Huequen', 'Los Confines', 'Los Sauces', 'Tijeral y Renaico'],
  'Victoria': ['Curacautín', 'Perquenco', 'Tolhuaca', 'Traiguen 1', 'Traiguen 2', 'Victoria 1', 'Victoria 2'],
  'Temuco Ñielol': ['Catrihuala 1', 'Catrihuala 2', 'Caupolicán 1', 'Lautaro 1', 'Lautaro 2', 'Lican Ray 1', 'Lican Ray 2', 'Quirihue 1', 'Quirihue 2', 'Vilcun', 'Ñielol 1', 'Ñielol 2'],
  'Temuco Cautín': ['Carahue', 'Cautin 2', 'Cautín 1', 'Cunco', 'Labranza 1', 'Labranza 2', 'Llaima 1', 'Llaima 2', 'Maquehue 1', 'Maquehue 2', 'Nueva Imperial'],
  'Villarrica': ['Ancahual', 'Freire', 'Loncoche', 'MLS Pucón', 'Pitrufquen 1', 'Pitrufquen 2', 'Pucón 1', 'Pucón 2', 'Volcán 1', 'Volcán 2']
}
# canonical[(zone, area)] -> canonical zone/area strings (identical objects
# from ZONES), used to normalize whatever the export's whitespace/encoding is.
canonical = {}
for z, areas in ZONES.items():
    for a in areas:
        canonical[(z.strip(), a.strip())] = (z, a)

raw = pd.read_excel(SRC, header=None)
hdr = raw.index[raw.apply(lambda r: (r == 'Zone').any(), axis=1)][0]
df = pd.read_excel(SRC, header=hdr)
df.columns = [str(c).strip() for c in df.columns]
df = df.dropna(subset=['Area']).copy()
df['Position'] = df['Position'].fillna('')
df['Zone'] = df['Zone'].astype(str).str.strip()
df['District'] = df['District'].astype(str).str.strip()
df['Area'] = df['Area'].astype(str).str.strip()

# Drop rows whose (Zone, Area) isn't one of the 10 CCSM teaching zones/areas
# (e.g. the 'Service' zone — a service missionary, not a teaching assignment).
dropped = []
keep_mask = []
for _, r in df.iterrows():
    key = (r['Zone'], r['Area'])
    if key in canonical:
        keep_mask.append(True)
    else:
        keep_mask.append(False)
        dropped.append(key)
df = df[keep_mask]
if dropped:
    print('// dropped %d row(s) not in CCSM_ZONES: %s' % (len(dropped), sorted(set(dropped))), file=sys.stderr)

rows, code = [], 0
for (zone, district, area), g in df.groupby(['Zone', 'District', 'Area'], sort=True):
    czone, carea = canonical[(zone, area)]
    code += 1
    names = [n for n in g['Name'].fillna('') if n]
    pos = ' '.join(g['Position'])
    flag = lambda *codes: 'TRUE' if any(c in pos for c in codes) else 'FALSE'
    comp1 = names[0] if len(names) > 0 else ''
    comp2 = ' / '.join(names[1:]) if len(names) > 1 else ''
    rows.append([
        'A%03d' % code, carea, czone, district,
        comp1, '',          # Companion1_Name, blank email
        comp2, '',          # Companion2_Name, blank email
        flag('(DL)'), flag('(ZL1)', '(ZL2)'), flag('(STL1)', '(STL2)', '(STLT)'),
        flag('(AP)'), 'FALSE', 'TRUE',
    ])
print('var CCSM_MISSION_ORG_ROWS = [')
for i, r in enumerate(rows):
    comma = ',' if i < len(rows) - 1 else ''
    print(' ' + json.dumps(r, ensure_ascii=False) + comma)
print('];')
print('// rows: %d' % len(rows), file=sys.stderr)
