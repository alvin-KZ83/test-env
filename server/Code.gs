/**
 * Quiz result collector — Google Apps Script web app.
 *
 * Receives encrypted quiz results from test_runner.html and appends one row
 * per submission to a Google Sheet. The sheet only ever stores ciphertext
 * plus a little cleartext metadata (participant id / lecture / test / time)
 * so you can watch completions come in without decrypting.
 *
 * Setup: see COLLECTION_SETUP.md in the repo. In short:
 *   1. Create a Google Sheet, copy its ID from the URL, paste below.
 *   2. Extensions -> Apps Script, replace the file with this, Save.
 *   3. Deploy -> New deployment -> Web app
 *        Execute as:  Me
 *        Who has access:  Anyone
 *      Copy the /exec URL into COLLECT_URL in test_runner.html.
 */

// ---- config -------------------------------------------------------------
var SHEET_ID = "1s98uot70xP-xAkO9Oo9zOeSHrspS7WwrNBIFIEbZLv8";
var SHEET_NAME = "responses";
// Optional: set the same non-empty string as COLLECT_TOKEN in test_runner.html
// to reject submissions that don't carry it. Not a real secret.
var SHARED_TOKEN = "";
// -----------------------------------------------------------------------

var HEADERS = [
  "received_at", "participant_id", "lecture", "test", "assigned_order",
  "finished_at", "alg", "ek", "iv", "ct"
];

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return json_({ ok: false, error: "empty request body" });
    }

    var body = JSON.parse(e.postData.contents);

    if (SHARED_TOKEN && body.token !== SHARED_TOKEN) {
      return json_({ ok: false, error: "bad or missing token" });
    }
    if (body.format !== "quiz-result-encrypted" || !body.ct || !body.ek || !body.iv) {
      return json_({ ok: false, error: "not an encrypted quiz result" });
    }

    var lock = LockService.getScriptLock();
    lock.waitLock(20000);
    try {
      var sheet = getSheet_();
      var m = body.meta || {};
      appendTextRow_(sheet, new Date(), [
        String(m.participant_id || ""),
        String(m.lecture || ""),
        String(m.test || ""),
        String(m.assigned_order || ""),
        String(m.finished_at || ""),
        String(body.alg || ""),
        String(body.ek),
        String(body.iv),
        String(body.ct)
      ]);
    } finally {
      lock.releaseLock();
    }

    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doGet() {
  return json_({ ok: true, service: "quiz-result-collector" });
}

function getSheet_() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

// Write a row whose text cells are stored verbatim. appendRow() lets Sheets
// parse values, so base64 starting with "+", "=" or "-" became a formula
// (#ERROR!, #NAME?) and the submission could no longer be decrypted.
// Formatting the cells as plain text ("@") before writing prevents that.
// Must run while the script lock is held, so the row number can't race.
function appendTextRow_(sheet, receivedAt, textValues) {
  var row = sheet.getLastRow() + 1;
  sheet.getRange(row, 1).setValue(receivedAt);
  var range = sheet.getRange(row, 2, 1, textValues.length);
  range.setNumberFormat("@");
  range.setValues([textValues]);
}

// Run once from the Apps Script editor (select selfTest -> Run) after
// deploying: writes formula-like strings to a temporary sheet, reads them
// back, deletes the sheet, and logs PASS / FAIL.
function selfTest() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var tmp = ss.insertSheet("selftest_" + new Date().getTime());
  var samples = ["+abc/def==", "=1+1", "-xyz", "@name", "#ERROR!", "Qt3kDiNR81PjVf89"];
  try {
    appendTextRow_(tmp, new Date(), samples);
    var back = tmp.getRange(1, 2, 1, samples.length).getValues()[0];
    var bad = samples.filter(function (s, i) { return back[i] !== s; });
    Logger.log(bad.length ? "FAIL: altered values " + JSON.stringify(bad) + " -> " + JSON.stringify(back)
                          : "PASS: all " + samples.length + " values stored verbatim");
  } finally {
    ss.deleteSheet(tmp);
  }
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
