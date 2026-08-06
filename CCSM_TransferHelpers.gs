// ── CCSM_TransferHelpers.gs ────────────────────────────────────────────────────
// Ported from Utah Provo's docs/AgentTransfer.gs (lines 144-155, 200-276,
// 771-845, 933-971, 1104-1177) — every at_ prefix renamed cct_. CCSM has no
// AgentTransfer.gs of its own, so these helpers (MISSION_ORG reading, zone
// dropdown structure reading, item cloning, routing repair) are ported fresh
// rather than reused from an existing file.

var CCT_MISSION_ORG_TAB = 'MISSION_ORG';
var CCT_TRANSFER_LOG_TAB = 'TRANSFER_LOG';

function cct_log_(fnName, result, details) {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CCT_TRANSFER_LOG_TAB);
  if (!sheet) {
    sheet = ss.insertSheet(CCT_TRANSFER_LOG_TAB);
    sheet.appendRow(['Timestamp', 'Function', 'Result', 'Details']);
    sheet.setFrozenRows(1);
  }
  sheet.appendRow([new Date(), fnName, result, details]);
}

function cct_loadMissionOrg_() {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(CCT_MISSION_ORG_TAB);
  if (!sheet) throw new Error('MISSION_ORG tab not found');
  var data = sheet.getDataRange().getValues();
  if (data.length < 2) throw new Error('MISSION_ORG is empty');

  var headers = data[0].map(function(h) { return String(h).trim(); });
  var map     = {};

  for (var i = 1; i < data.length; i++) {
    var obj = {};
    headers.forEach(function(h, idx) { obj[h] = String(data[i][idx] || '').trim(); });
    var key = (obj['Area_Name'] || '').toLowerCase().trim();
    if (key) map[key] = { obj: obj, rowIndex: i, headers: headers };
  }

  return { map: map, headers: headers, data: data, sheet: sheet };
}

// Keyed off Area_Name, not the Is_* flags — a real teaching-area row can
// legitimately carry a leadership flag when its companion holds that calling.
function cct_isLeadershipRow_(obj) {
  var name = (obj['Area_Name'] || '').trim();
  return /^(Mission President|Assistant to President|Zone Leader|Sister Training Leader -|District Leader -)/i.test(name);
}

function cct_isSeniorRow_(obj) {
  var name = (obj['Area_Name'] || '').trim();
  return /\bSenior\b/i.test(name);
}

function cct_isNonTeachingRow_(obj) {
  return cct_isLeadershipRow_(obj) || cct_isSeniorRow_(obj);
}

function cct_getOrgZones_() {
  var orgData = cct_loadMissionOrg_();
  var zones   = {};
  Object.keys(orgData.map).forEach(function(k) {
    var obj = orgData.map[k].obj;
    if ((obj['Active'] || '').toUpperCase() !== 'TRUE') return;
    if (cct_isNonTeachingRow_(obj)) return;
    var zone = (obj['Zone']      || '').toLowerCase().trim();
    var area = (obj['Area_Name'] || '').trim();
    if (!zone || !area) return;
    if (!zones[zone]) zones[zone] = [];
    zones[zone].push(area);
  });
  return zones;
}

function cct_normalizeZoneSectionTitle_(title) {
  return String(title || '')
    .replace(/\s+Zone Section\s*$/i, '')
    .toLowerCase()
    .trim();
}

function cct_readFormStructure_(formId) {
  var form  = FormApp.openById(formId);
  var items = form.getItems();

  var zoneItem = null;
  items.forEach(function(item) {
    if (item.getType() !== FormApp.ItemType.LIST) return;
    var t = item.getTitle().toLowerCase();
    if (t.indexOf('zone') >= 0 && t.indexOf('area') < 0) zoneItem = item.asListItem();
  });
  if (!zoneItem) throw new Error('Could not find "What zone are you in?" list item in the form.');

  var pageBreakItems = [];
  items.forEach(function(item) {
    if (item.getType() === FormApp.ItemType.PAGE_BREAK) {
      pageBreakItems.push(item.asPageBreakItem());
    }
  });

  var pbItemIndices = [];
  items.forEach(function(item, idx) {
    if (item.getType() === FormApp.ItemType.PAGE_BREAK) pbItemIndices.push(idx);
  });

  var zoneSections = pageBreakItems.map(function(pb, sectionIdx) {
    var startIdx = pbItemIndices[sectionIdx];
    var endIdx   = sectionIdx + 1 < pbItemIndices.length
      ? pbItemIndices[sectionIdx + 1]
      : items.length;

    var sectionItems = items.slice(startIdx, endIdx);

    var areaItem = null;
    sectionItems.forEach(function(item) {
      if (item.getType() === FormApp.ItemType.LIST &&
          item.getTitle().toLowerCase().indexOf('area') >= 0 &&
          !areaItem) {
        areaItem = item.asListItem();
      }
    });

    return {
      pageBreak:       pb,
      zoneName:        cct_normalizeZoneSectionTitle_(pb.getTitle()) || null,
      areaItem:        areaItem,
      allSectionItems: sectionItems,
      sectionIdx:      sectionIdx
    };
  });

  return { form: form, zoneItem: zoneItem, zoneSections: zoneSections };
}

function cct_cloneItem_(form, sourceItem) {
  var type  = sourceItem.getType();
  var title = sourceItem.getTitle();
  switch (type) {
    case FormApp.ItemType.TEXT:
      return form.addTextItem().setTitle(title)
        .setRequired(sourceItem.asTextItem().isRequired());
    case FormApp.ItemType.PARAGRAPH_TEXT:
      return form.addParagraphTextItem().setTitle(title)
        .setRequired(sourceItem.asParagraphTextItem().isRequired());
    case FormApp.ItemType.MULTIPLE_CHOICE:
      var mc = sourceItem.asMultipleChoiceItem();
      return form.addMultipleChoiceItem().setTitle(title)
        .setChoiceValues(mc.getChoices().map(function(c) { return c.getValue(); }))
        .setRequired(mc.isRequired());
    case FormApp.ItemType.CHECKBOX:
      var cb = sourceItem.asCheckboxItem();
      return form.addCheckboxItem().setTitle(title)
        .setChoiceValues(cb.getChoices().map(function(c) { return c.getValue(); }))
        .setRequired(cb.isRequired());
    case FormApp.ItemType.DATE:
      return form.addDateItem().setTitle(title)
        .setRequired(sourceItem.asDateItem().isRequired());
    case FormApp.ItemType.LIST:
      var li = sourceItem.asListItem();
      return form.addListItem().setTitle(title)
        .setChoiceValues(li.getChoices().map(function(c) { return c.getValue(); }))
        .setRequired(li.isRequired());
    case FormApp.ItemType.SCALE:
      var si = sourceItem.asScaleItem();
      return form.addScaleItem().setTitle(title)
        .setBounds(si.getLowerBound(), si.getUpperBound())
        .setRequired(si.isRequired());
    default:
      Logger.log('cct_cloneItem_: unknown type ' + type + ' for "' + title + '" — added as text');
      return form.addTextItem().setTitle(title);
  }
}

function cct_repairFormRouting_(formId) {
  var form  = FormApp.openById(formId);
  var items = form.getItems();

  var zoneItem = null;
  items.forEach(function(item) {
    if (item.getType() !== FormApp.ItemType.LIST) return;
    var t = item.getTitle().toLowerCase();
    if (t.indexOf('zone') >= 0 && t.indexOf('area') < 0) zoneItem = item.asListItem();
  });
  if (!zoneItem) throw new Error('Zone dropdown not found in form.');

  var orgZones = cct_getOrgZones_();

  var areaToZone = {};
  Object.keys(orgZones).forEach(function(zone) {
    orgZones[zone].forEach(function(area) {
      areaToZone[area.toLowerCase()] = zone;
    });
  });

  var pbItemIndices = [];
  items.forEach(function(item, idx) {
    if (item.getType() === FormApp.ItemType.PAGE_BREAK) pbItemIndices.push(idx);
  });

  var pbByZone = {};
  pbItemIndices.forEach(function(startIdx, sectionIdx) {
    var endIdx = sectionIdx + 1 < pbItemIndices.length
      ? pbItemIndices[sectionIdx + 1]
      : items.length;
    var pb = items[startIdx].asPageBreakItem();
    for (var j = startIdx + 1; j < endIdx; j++) {
      if (items[j].getType() === FormApp.ItemType.LIST &&
          items[j].getTitle().toLowerCase().indexOf('area') >= 0) {
        var choices = items[j].asListItem().getChoices();
        for (var c = 0; c < choices.length; c++) {
          var zone = areaToZone[choices[c].getValue().toLowerCase()];
          if (zone) { pbByZone[zone] = pb; break; }
        }
        break;
      }
    }
  });

  var orgDataForDisplay = cct_loadMissionOrg_();
  var zoneDisplayMap = {};
  Object.keys(orgDataForDisplay.map).forEach(function(k) {
    var obj = orgDataForDisplay.map[k].obj;
    if ((obj['Active'] || '').toUpperCase() !== 'TRUE') return;
    if (cct_isNonTeachingRow_(obj)) return;
    var dn = (obj['Zone'] || '').trim();
    if (dn) zoneDisplayMap[dn.toLowerCase()] = dn;
  });

  var orgZoneNames = Object.keys(orgZones).sort();
  var missing = [];
  var newChoices = orgZoneNames.map(function(zoneName) {
    var pb = pbByZone[zoneName];
    var dn = zoneDisplayMap[zoneName] || zoneName;
    if (!pb) { missing.push(zoneName); return zoneItem.createChoice(dn); }
    return zoneItem.createChoice(dn, pb);
  });
  zoneItem.setChoices(newChoices);

  return { zonesRouted: orgZoneNames.length - missing.length, zonesTotal: orgZoneNames.length, missing: missing };
}
