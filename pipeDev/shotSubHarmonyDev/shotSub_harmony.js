// ------------------------------------------------------------
// shotSub_harmony.js
//
// Toon Boom Harmony companion to pipeDev/shotSubDev/shotSub.py (Maya).
// See shotSub_harmony_design.md in this folder for the full design
// discussion this was built from -- workflow, what's reused vs new, and
// an explicit list of open/unverified items. Read that before changing
// this file.
//
// IMPORTANT -- this file has never been run against a real Harmony
// session (none was available in the environment it was written in).
// Every call here is written against Toon Boom's own documented scripting
// reference, but several pieces are flagged VERIFY below and should be
// treated as a first pass to debug against a live session, not finished,
// tested code the way the Maya-side work in this repo normally is.
//
// Written in conservative ES5-style JS (var/function, no arrow functions
// or let/const) to match Harmony's QtScript-based engine and the style of
// existing community Harmony scripts, rather than assuming a modern JS
// engine is guaranteed.
//
// Shelf/toolbar button:
//   include("shotSub_harmony.js");
//   shotSub_show();
// ------------------------------------------------------------

// ------------------------------------------------------------
// Fixed names -- what this tool creates and later finds/replaces. Keeping
// these as constants (not re-derived per shot) is what lets "Create
// ShotSub" safely delete-then-recreate its own nodes without touching
// anything the student built themselves.
// ------------------------------------------------------------
var SHOTSUB_WRITE_NODE_NAME = "Write_playblast";
var SHOTSUB_BURNIN_NODE_NAME = "BurnIn_playblast";
var SHOTSUB_GROUP = "Top"; // node.root() -- new nodes are added at the top level, not inside whatever group the student's Composite happens to live in, so they're always easy to find again by name.

// Resolved once at load time -- see resolvePythonAndBridge() below.
var SHOTSUB_BRIDGE_DIR = specialFolders.userScripts + "/shotSubHarmony"; // VERIFY: adjust to wherever this folder actually gets deployed to on a student machine.


// ------------------------------------------------------------
// Node discovery -- walks the whole node tree from node.root(), collecting
// every node of a given type regardless of nesting or student-given name.
// Confirmed API: node.numberOfSubNodes(), node.subNode(), node.type(),
// node.isGroup(), node.root(). See "Node/render/scene scripting" sources
// in the design doc.
// ------------------------------------------------------------
function shotSub_findNodesByType(nodeType) {
  var results = [];

  function walk(parentPath) {
    var count = node.numberOfSubNodes(parentPath);
    for (var i = 0; i < count; i++) {
      var childPath = node.subNode(parentPath, i);
      if (node.type(childPath) == nodeType) {
        results.push(childPath);
      }
      if (node.isGroup(childPath)) {
        walk(childPath);
      }
    }
  }

  walk(node.root());
  return results;
}

function shotSub_findCompositeNodes() {
  return shotSub_findNodesByType("COMPOSITE");
}


// ------------------------------------------------------------
// Attribute discovery helper -- Toon Boom's own scripting docs do not
// enumerate WriteNode's settable attributes (Image Sequence on/off, Movie
// on/off + format, Movie Folder/Filename -- the fields in the Layer
// Properties panel the design doc's screenshot shows). Rather than
// guessing attribute keyword strings and silently setting the wrong ones,
// this prints every attribute Harmony reports on a given node into the
// Message Log, keyword and current value, via node.getAttrList() --
// genuinely core, high-confidence Harmony scripting API (all node
// attribute access goes through this), unlike the Write-node-specific
// setters which aren't documented at all.
//
// One-time setup step before shotSub_configureWriteNode() below can be
// trusted: manually create a Write node in a scratch scene, configure it
// by hand exactly like the design doc's screenshot (Image Sequence off,
// Movie on, H.264/MPEG-4 (*.mov), etc.), then run:
//     shotSub_dumpNodeAttributes("Top/<that node's name>");
// and read the keywords back out of the Message Log. Use those exact
// keywords in WRITE_NODE_ATTRS below -- do not guess.
// ------------------------------------------------------------
function shotSub_dumpNodeAttributes(nodePath) {
  var attrs = node.getAttrList(nodePath, 1);
  MessageLog.trace("shotSub: attributes on " + nodePath + " --");
  for (var i = 0; i < attrs.length; i++) {
    var attr = attrs[i];
    var value;
    try {
      value = attr.textValueAt ? attr.textValueAt(1) : node.getTextAttr(nodePath, 1, attr.keyword());
    } catch (e) {
      value = "<unreadable>";
    }
    MessageLog.trace("  " + attr.keyword() + " = " + value);
  }
}

// VERIFY: every keyword below is an unconfirmed placeholder, not a value
// pulled from Toon Boom's docs (which don't document these) or from a
// live Harmony session (none was available while writing this). Run
// shotSub_dumpNodeAttributes() per the instructions above and correct
// these before relying on shotSub_configureWriteNode().
var WRITE_NODE_ATTRS = {
  imageSequenceEnabled: "DRAWING_TYPE",   // VERIFY
  movieEnabled: "MOVIE",                  // VERIFY
  movieFormat: "MOVIE_FORMAT",            // VERIFY
  movieFolder: "MOVIE_PATH_FOLDER",       // VERIFY
  movieFilename: "MOVIE_PATH_FILENAME"    // VERIFY
};


// ------------------------------------------------------------
// Node creation -- confirmed API: node.add(parentGroup, name, type, x, y, z).
// node.link()'s exact parameter order is NOT confirmed from docs alone;
// the call below follows the commonly-cited Harmony convention
// (outNode, outPort, inNode, inPort, inPortAlreadyLinked, createOnConflict)
// -- VERIFY against a live session before trusting the resulting
// connections are actually made as intended.
// ------------------------------------------------------------
function shotSub_deleteExistingToolNodes() {
  var writePath = SHOTSUB_GROUP + "/" + SHOTSUB_WRITE_NODE_NAME;
  var burnInPath = SHOTSUB_GROUP + "/" + SHOTSUB_BURNIN_NODE_NAME;
  if (node.type(writePath) == "WRITE") {
    node.deleteNode(writePath);
  }
  if (node.type(burnInPath) == "BURN_IN") { // VERIFY: exact type string for the Burn-In node
    node.deleteNode(burnInPath);
  }
}

function shotSub_createToolNodes(compositeNodePath) {
  shotSub_deleteExistingToolNodes();

  var burnInPath = node.add(SHOTSUB_GROUP, SHOTSUB_BURNIN_NODE_NAME, "BURN_IN", 0, 0, 0); // VERIFY: exact type string
  var writePath = node.add(SHOTSUB_GROUP, SHOTSUB_WRITE_NODE_NAME, "WRITE", 0, 100, 0);

  // Composite (out port 0) -> Burn-In (in port 0) -> Write (in port 0).
  // A Composite's output can fan out to multiple destinations, so this
  // taps an additional connection rather than disturbing whatever the
  // Composite already feeds (e.g. the scene's own default Write node).
  node.link(compositeNodePath, 0, burnInPath, 0, false, true); // VERIFY parameter order
  node.link(burnInPath, 0, writePath, 0, false, true);         // VERIFY parameter order

  shotSub_configureWriteNode(writePath);

  return {burnIn: burnInPath, write: writePath};
}

function shotSub_configureWriteNode(writePath) {
  // See WRITE_NODE_ATTRS's VERIFY note above -- do not trust this
  // function until those keywords are confirmed against a live session.
  node.setTextAttr(writePath, WRITE_NODE_ATTRS.imageSequenceEnabled, 1, "0");
  node.setTextAttr(writePath, WRITE_NODE_ATTRS.movieEnabled, 1, "1");
  node.setTextAttr(writePath, WRITE_NODE_ATTRS.movieFormat, 1, "H.264/MPEG-4");
  // Movie Folder / Filename left at whatever Harmony defaults to unless
  // overridden -- see shotSub_harmony_design.md's open items (the
  // screenshot's "frames" folder value wasn't confirmed as intentional).
}


// ------------------------------------------------------------
// Rendering -- confirmed API: render.renderNodes(nodeList, from, to),
// render.renderFinished signal. Harmony's older QtScript engine connects
// signals via <signal>.connect(context, handler), the same pattern as
// widget.clicked.connect(...) in Harmony UI scripts -- used here on that
// assumption; VERIFY if renderFinished turns out not to be a real Qt
// signal object on this Harmony version.
// ------------------------------------------------------------
function shotSub_renderAndThen(writePath, fromFrame, toFrame, onComplete) {
  var handler = function () {
    render.renderFinished.disconnect(this, handler); // one-shot
    onComplete();
  };
  render.renderFinished.connect(this, handler);
  render.renderNodes([writePath], fromFrame, toFrame);
}

function shotSub_findRenderedMovie(writePath) {
  var wn = new WriteNode(writePath); // VERIFY: confirm WriteNode is constructed this way, not accessed via a different global accessor
  var dir = wn.movieDir();
  var name = wn.movieName();
  if (!dir || !name) {
    return null;
  }
  return dir + "/" + name; // VERIFY: confirm movieName() doesn't already include the extension/full path on its own
}


// ------------------------------------------------------------
// External process handoff -- confirmed API: Process2/System classes
// exist for launching external processes from Harmony JS. Exact
// synchronous-vs-signal-based behaviour of Process2 is unconfirmed (see
// design doc) -- written here assuming a finished-signal, matching the
// render class's own pattern, since blocking Harmony's UI thread on a
// slow ShotGrid upload would be a poor experience if wrong in the other
// direction.
// ------------------------------------------------------------
function shotSub_resolvePythonExecutable() {
  // VERIFY: point this at the bundled/portable Python interpreter once
  // one is set up for deployment (see design doc's "Python bridge
  // interpreter" section) -- this env-var override plus a bare "python"
  // PATH fallback is a stopgap for local testing only, not the intended
  // production lookup.
  var envOverride = System.getenv ? System.getenv("SHOTSUB_HARMONY_PYTHON") : null; // VERIFY: exact System env-read call name
  return envOverride || "python";
}

function shotSub_writeTempJson(obj, filename) {
  var path = specialFolders.temp + "/" + filename;
  var file = new PermanentFile(path);
  var stream = new File(file.path);
  stream.open(FileAccess.WriteOnly);
  stream.write(JSON.stringify(obj));
  stream.close();
  return path;
}

function shotSub_readTempJson(path) {
  var file = new File(path);
  file.open(FileAccess.ReadOnly);
  var text = file.read();
  file.close();
  return JSON.parse(text);
}

function shotSub_publish(entityType, entityId, moviePath, notes, fps, onComplete) {
  var stamp = String(Date.now ? Date.now() : new Date().getTime());
  var inputPath = shotSub_writeTempJson({
    entity_type: entityType,
    entity_id: entityId,
    movie_path: moviePath,
    notes: notes || null,
    fps: fps || null
  }, "shotSub_bridge_in_" + stamp + ".json");
  var outputPath = specialFolders.temp + "/shotSub_bridge_out_" + stamp + ".json";

  var pythonExe = shotSub_resolvePythonExecutable();
  var bridgeScript = SHOTSUB_BRIDGE_DIR + "/shotgrid_bridge.py";

  var proc = new Process2([pythonExe, bridgeScript, inputPath, outputPath]); // VERIFY: Process2 constructor signature
  proc.finished.connect(this, function () { // VERIFY: signal name -- see design doc's open item on Process2
    var result;
    try {
      result = shotSub_readTempJson(outputPath);
    } catch (e) {
      result = {success: false, error: "Could not read bridge result: " + e};
    }
    onComplete(result);
  });
  proc.start();
}


// ------------------------------------------------------------
// ShotGrid link file -- same shotgrid_link.json convention as the Maya
// tool (see shotSub.py's write_shotgrid_link()/read_shotgrid_link()), so
// both tools agree on "which shot is this" if a scene/project ever needs
// to carry both. Written/read relative to the current scene's own folder
// (see shotSub_harmony_design.md -- no mirrored scenes/images root here).
// ------------------------------------------------------------
function shotSub_linkFilePath() {
  return scene.currentProjectPath() + "/shotgrid_link.json"; // VERIFY: confirm this is the right call for "this scene's own folder" in a standalone (non-database) scene
}

function shotSub_readShotgridLink() {
  var path = shotSub_linkFilePath();
  var file = new PermanentFile(path);
  if (!file.exists) {
    return null;
  }
  try {
    return shotSub_readTempJson(path);
  } catch (e) {
    MessageLog.trace("shotSub: could not read shotgrid_link.json -- " + e);
    return null;
  }
}


// ------------------------------------------------------------
// UI
//
// Built directly from Harmony's exposed Qt bindings (QDialog/QComboBox/
// etc constructible from script), the long-established pattern in
// community Harmony tools, rather than UiLoader + a separate .ui file --
// keeps this to one file. VERIFY overall widget behaviour on a live
// session; the individual widget classes/constructors themselves are a
// well-established, high-confidence part of Harmony's scripting surface.
// ------------------------------------------------------------
function ShotSubHarmonyDialog() {
  this.dialog = new QDialog();
  this.dialog.windowTitle = "shotSub";
  this.dialog.setLayout(new QVBoxLayout());

  this.dialog.layout().addWidget(new QLabel("Composite node:"));
  this.compositeCombo = new QComboBox();
  this.dialog.layout().addWidget(this.compositeCombo);

  var frameRow = new QHBoxLayout();
  frameRow.addWidget(new QLabel("Start:"));
  this.startField = new QLineEdit();
  frameRow.addWidget(this.startField);
  frameRow.addWidget(new QLabel("End:"));
  this.endField = new QLineEdit();
  frameRow.addWidget(this.endField);
  var frameRowWidget = new QWidget();
  frameRowWidget.setLayout(frameRow);
  this.dialog.layout().addWidget(frameRowWidget);

  this.dialog.layout().addWidget(new QLabel("Notes (sent with this publish):"));
  this.notesField = new QTextEdit();
  this.dialog.layout().addWidget(this.notesField);

  this.statusLabel = new QLabel("");
  this.dialog.layout().addWidget(this.statusLabel);

  this.createButton = new QPushButton("Create ShotSub");
  this.dialog.layout().addWidget(this.createButton);

  this.publishButton = new QPushButton("Publish ShotSub");
  this.publishButton.enabled = false;
  this.dialog.layout().addWidget(this.publishButton);

  this._renderedMoviePath = null;

  this._populateComposites();
  this._populateFrameRange();
  this._connectSignals();
}

ShotSubHarmonyDialog.prototype._populateComposites = function () {
  var composites = shotSub_findCompositeNodes();
  this.compositeCombo.clear();
  for (var i = 0; i < composites.length; i++) {
    // Show the node's own name (last path segment) but keep the full
    // path around via itemData, since students can duplicate/rename
    // freely and two Composites could share a short name in different
    // groups.
    var shortName = composites[i].split("/").pop();
    this.compositeCombo.addItem(shortName, composites[i]);
  }
};

ShotSubHarmonyDialog.prototype._populateFrameRange = function () {
  this.startField.text = String(scene.getStartFrame());
  this.endField.text = String(scene.getStopFrame());
};

ShotSubHarmonyDialog.prototype._connectSignals = function () {
  var self = this;
  this.createButton.clicked.connect(this, function () { self._onCreate(); });
  this.publishButton.clicked.connect(this, function () { self._onPublish(); });
};

ShotSubHarmonyDialog.prototype._onCreate = function () {
  var index = this.compositeCombo.currentIndex;
  if (index < 0) {
    this.statusLabel.text = "No Composite node selected.";
    return;
  }
  var compositePath = this.compositeCombo.itemData(index);
  var startFrame = parseInt(this.startField.text, 10);
  var endFrame = parseInt(this.endField.text, 10);

  this.statusLabel.text = "Rendering...";
  this.publishButton.enabled = false;

  var nodes = shotSub_createToolNodes(compositePath);
  var self = this;
  shotSub_renderAndThen(nodes.write, startFrame, endFrame, function () {
    var moviePath = shotSub_findRenderedMovie(nodes.write);
    if (!moviePath) {
      self.statusLabel.text = "Render finished but no movie file was found -- check Write node settings.";
      return;
    }
    self._renderedMoviePath = moviePath;
    self.statusLabel.text = "Rendered: " + moviePath;
    self.publishButton.enabled = true;
    shotSub_launchPreview(moviePath);
  });
};

ShotSubHarmonyDialog.prototype._onPublish = function () {
  if (!this._renderedMoviePath) {
    this.statusLabel.text = "Nothing to publish yet -- click Create ShotSub first.";
    return;
  }
  var link = shotSub_readShotgridLink();
  if (!link) {
    this.statusLabel.text = "This shot isn't linked to ShotGrid yet.";
    return;
  }

  this.statusLabel.text = "Publishing...";
  this.publishButton.enabled = false;

  var notes = this.notesField.plainText;
  var fps = scene.getFrameRate();
  var self = this;
  shotSub_publish(
    link.sg_entity_type || "Shot",
    link.sg_entity_id,
    this._renderedMoviePath,
    notes,
    fps,
    function (result) {
      if (result.success) {
        self.statusLabel.text = "Published (ShotGrid Version id " + result.sg_version_id + ").";
      } else {
        self.statusLabel.text = "Publish failed: " + result.error;
        self.publishButton.enabled = true;
      }
    }
  );
};

function shotSub_launchPreview(moviePath) {
  // Deliberately does not try to embed a video widget in the tool's own
  // dialog -- QtMultimedia's availability inside Harmony's Qt bindings is
  // unconfirmed (see design doc). Launching the OS's own default player
  // is the same "hand off to something that definitely knows how to play
  // a movie" approach shotSub.py takes with RV, just via the OS instead.
  if (about.isWindowsArch()) { // VERIFY: exact platform-check call name
    System.launch(moviePath); // VERIFY: exact "open with default app" call
  } else {
    Process2(["open", moviePath]).start(); // VERIFY: mac path, untested
  }
}


// ------------------------------------------------------------
// Entry point
// ------------------------------------------------------------
var shotSub_dialogInstance = null;

function shotSub_show() {
  shotSub_dialogInstance = new ShotSubHarmonyDialog();
  shotSub_dialogInstance.dialog.show();
}
