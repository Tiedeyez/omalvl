pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons

// OmaLvL: 17 skills in six areas, levelled by using your Omarchy machine, a Rice rating,
// quests, contracts, signals, theme seasons, relics, the keybind tree and a journal. skills.py
// is the engine and daemon; `omalvl` is its CLI. Everything here is drawn on a pixel grid in the active theme's colours:
// stepped corners and block shading, like the Omarchy wordmark.
Panel {
  id: root
  ipcTarget: "omalvl"

  // ---- engine + state ---------------------------------------------------------
  readonly property string here: decodeURIComponent(Qt.resolvedUrl(".").toString().replace(/^file:\/\//, ""))
  readonly property string enginePath: here + "skills.py"
  readonly property string python: "/usr/bin/python3"
  // Named `sk`, not `data`: `data` is Item's own default property.
  property var sk: ({ skills: [], questLog: [], total: 0, maxTotal: 1700 })
  property var art: ({ icons: {}, font: {} })
  property string tab: "skills"
  property string confirmKey: ""       // two-click actions: the first click arms, the second runs
  property string expandedQuest: ""
  property string guideSkill: ""
  property var guide: null
  property string hoverSkill: ""
  property string busy: ""
  onTabChanged: { confirmKey = ""; guideSkill = ""; dissolve.play() }
  onGuideSkillChanged: {
    root.guide = null
    dissolve.play()
    if (guideSkill === "") return
    guideProc.command = [root.python, "-I", root.enginePath, "guide", guideSkill, "--json"]
    guideProc.running = true
  }

  Process {
    id: artProc
    command: [root.python, "-I", root.enginePath, "icons", "--json"]
    running: true
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: { try { root.art = JSON.parse(text) } catch (e) {} }
    }
  }
  Process {
    id: guideProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: { try { root.guide = JSON.parse(text) } catch (e) {} }
    }
  }
  Process { id: runner; onRunningChanged: if (!running) root.busy = "" }
  function run(args) {
    if (runner.running) return
    root.busy = args.join(" ")
    runner.command = [root.python, "-I", root.enginePath].concat(args)
    runner.running = true
    root.confirmKey = ""
  }
  function twoClick(key, args) {
    if (root.confirmKey === key) root.run(args)
    else root.confirmKey = key
  }

  property real lastDropT: -1
  function reload(text) {
    try { root.sk = JSON.parse(text) } catch (e) { return }
    var d = root.sk.dropInfo
    if (!d) return
    if (root.lastDropT < 0) { root.lastDropT = d.t; return }   // first load: no replay
    if (d.t > root.lastDropT) {
      root.lastDropT = d.t
      if (Date.now() / 1000 - d.t < 15) drops.show(d.gains, d.ups || [], d.milestone || 0)
    }
  }
  Process {
    id: stateProc
    command: [root.python, "-I", root.enginePath, "panel-state"]
    running: true
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.reload(text)
    }
    onExited: stateRefresh.restart()
  }
  Timer {
    id: stateRefresh
    interval: 3000
    repeat: false
    onTriggered: if (!stateProc.running) stateProc.running = true
  }
  // The activity sampler (single instance; extra copies exit on the lock).
  Process {
    id: daemon
    command: [root.python, "-I", root.enginePath, "daemon"]
    running: true
    onExited: daemonRespawn.start()
  }
  Timer { id: daemonRespawn; interval: 5000; onTriggered: daemon.running = true }

  //   omarchy-shell omalvl.ui tab quests  |  ... guide shell  |  ... quest neovim
  IpcHandler {
    target: "omalvl.ui"
    function tab(name: string): void { root.tab = name; root.open() }
    function quest(id: string): void { root.tab = "quests"; root.expandedQuest = id; root.open() }
    function guide(skill: string): void { root.tab = "skills"; root.guideSkill = skill; root.open() }
  }

  // ---- data views ---------------------------------------------------------------
  readonly property var skills: sk.skills || []
  readonly property var quests: sk.questLog || []
  readonly property var activity: sk.activity || []
  readonly property var diary: sk.diaryLog || []
  readonly property var contract: sk.contractInfo || ({})
  readonly property var signal: sk.signalInfo || null
  readonly property int tokens: sk.tokenCount || 0
  readonly property var season: sk.season || ({})
  readonly property var tree: sk.treeInfo || []
  readonly property var relics: sk.relicInfo || []
  readonly property var skins: sk.skins || []
  readonly property string skin: sk.skin || "plain"
  readonly property var sysop: sk.sysopInfo || null
  readonly property var companions: sk.companionLog || []
  readonly property var coll: sk.collectionLog || ({})
  readonly property var jobs: sk.jobInfo || []
  readonly property var streak: sk.streakInfo || ({})
  readonly property var marks: sk.marks || ({})
  readonly property var rice: sk.rice || ({ rating: 10, rank: "Fresh install", areas: [], next: null, weakest: null })
  readonly property int maxLevel: sk.maxLevel || 100
  readonly property int total: sk.total || 0
  readonly property int qp: sk.questPoints || 0
  readonly property int maxQp: sk.maxQuestPoints || 0
  readonly property int ripe: jobs.filter(function(p) { return p.done > 0 }).length
  property real nowS: Date.now() / 1000
  Timer { interval: 20000; running: true; repeat: true; onTriggered: root.nowS = Date.now() / 1000 }
  readonly property var surge: sk.surgeInfo && sk.surgeInfo.until > nowS ? sk.surgeInfo : null
  function skill(key) {
    for (var i = 0; i < skills.length; i++) if (skills[i].key === key) return skills[i]
    return null
  }
  function nameOf(key) { var s = skill(key); return s ? s.name : key }
  function skillsOf(area) { return skills.filter(function(s) { return s.area === area }) }

  // ---- theme ---------------------------------------------------------------------
  // The engine reads the theme's colors.toml (named colours); the shell's own tokens
  // are the fallback.
  readonly property var pal: sk.palette || ({})
  function pc(name, fallback) { var v = pal[name]; return v ? v : fallback }
  readonly property color fg: pc("foreground", Color.foreground)
  readonly property color bg: pc("background", Color.background)
  readonly property color accent: pc("accent", Color.accent)
  readonly property color well: pc("dark_background", Qt.darker(bg, 1.25))
  readonly property color raised: pc("lighter_background", Qt.lighter(bg, 1.35))
  readonly property color dim: Qt.rgba(fg.r, fg.g, fg.b, 0.78)
  readonly property color faint: Qt.rgba(fg.r, fg.g, fg.b, 0.18)
  function tint(name) { return pc(name || "", accent) }
  readonly property string font: Style.font.family

  // ---- pixel grid ------------------------------------------------------------------
  // `u` is one pixel of pixel art in screen pixels: always whole, so blocks stay crisp.
  readonly property int u: Math.max(2, Math.round(Style.font.body / 7))
  readonly property bool reduceMotion: !!(sk.settings && sk.settings.reduceMotion)

  function n(v) { return Number(v || 0).toLocaleString(Qt.locale(), "f", 0) }
  function ago(t) {
    var s = Math.max(0, Math.floor(Date.now() / 1000 - t))
    if (s < 60) return "now"
    if (s < 3600) return Math.floor(s / 60) + "m ago"
    if (s < 86400) return Math.floor(s / 3600) + "h ago"
    return Math.floor(s / 86400) + "d ago"
  }
  function dur(sec) {
    if (!sec) return "-"
    var m = Math.floor(sec / 60), h = Math.floor(m / 60)
    return h > 0 ? h + "h " + (m % 60) + "m" : m + "m"
  }

  // A 12x12 icon from icons.py, painted cell by cell in theme colours.
  component PixelArt: Canvas {
    id: pa
    property string name: ""
    property color tint: root.accent
    property color ink: root.fg
    property color hi: root.accent
    property int cell: root.u
    property bool ghost: false          // not yet earned: drawn as a faint silhouette
    readonly property var rows: (root.art.icons && root.art.icons[name]) || []
    width: 12 * cell
    height: 12 * cell
    onRowsChanged: requestPaint()
    onTintChanged: requestPaint()
    onInkChanged: requestPaint()
    onHiChanged: requestPaint()
    onGhostChanged: requestPaint()
    onCellChanged: requestPaint()
    onPaint: {
      var c = getContext("2d")
      c.reset()
      var shade = Qt.rgba(ink.r, ink.g, ink.b, 0.35)
      var silhouette = Qt.rgba(ink.r, ink.g, ink.b, 0.16)
      for (var y = 0; y < rows.length; y++) {
        var r = rows[y]
        for (var x = 0; x < r.length; x++) {
          var ch = r[x]
          if (ch === " ") continue
          c.fillStyle = ghost ? silhouette
            : (ch === "#" ? ink : (ch === "a" ? tint : (ch === "b" ? hi : shade)))
          c.fillRect(x * cell, y * cell, cell, cell)
        }
      }
    }
  }

  // Text in the 5x7 pixel face (pixelfont.py): headings and big numbers.
  component PixelText: Canvas {
    id: pt
    property string text: ""
    property int cell: root.u
    property color color: root.fg
    readonly property var glyphs: root.art.font || ({})
    readonly property string up: String(text).toUpperCase()
    width: Math.max(cell, up.length * 6 * cell - cell)
    height: 7 * cell
    Accessible.role: Accessible.StaticText
    Accessible.name: text
    onUpChanged: requestPaint()
    onColorChanged: requestPaint()
    onGlyphsChanged: requestPaint()
    onCellChanged: requestPaint()
    onPaint: {
      var c = getContext("2d")
      c.reset()
      c.fillStyle = color
      for (var i = 0; i < up.length; i++) {
        var g = glyphs[up[i]] || glyphs["?"]
        if (!g) continue
        for (var y = 0; y < 7; y++)
          for (var x = 0; x < 5; x++)
            if (g[y][x] === "#") c.fillRect((i * 6 + x) * cell, y * cell, cell, cell)
      }
    }
  }

  // A panel with stepped corners and a one-block border, like the wordmark's notches.
  component StepFrame: Canvas {
    id: sf
    property color fill: root.well
    property color edge: root.faint
    property int cell: root.u
    property int steps: 1
    property bool decor: false           // cards and tiles wear the chosen skin
    readonly property string skinId: decor ? root.skin : "plain"
    onSkinIdChanged: requestPaint()
    onFillChanged: requestPaint()
    onEdgeChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
      var c = getContext("2d")
      c.reset()
      var w = Math.floor(width), h = Math.floor(height), u = cell, s = u * steps
      if (w < 2 * s + u || h < 2 * s + u) return
      c.fillStyle = fill
      c.fillRect(s, u, w - 2 * s, h - 2 * u)
      c.fillRect(u, s, w - 2 * u, h - 2 * s)
      c.fillStyle = edge
      c.fillRect(s, 0, w - 2 * s, u)                 // top
      c.fillRect(s, h - u, w - 2 * s, u)             // bottom
      c.fillRect(0, s, u, h - 2 * s)                 // left
      c.fillRect(w - u, s, u, h - 2 * s)             // right
      for (var i = 1; i < steps; i++) {              // the stair between edges
        var a = i * u, b = (steps - i) * u
        c.fillRect(a, b, u, u); c.fillRect(w - a - u, b, u, u)
        c.fillRect(a, h - b - u, u, u); c.fillRect(w - a - u, h - b - u, u, u)
      }
      if (skinId === "plain") return
      var ac = root.accent
      if (skinId === "rivet") {                       // a rivet in each corner
        c.fillStyle = ac
        c.fillRect(3 * u, 3 * u, u, u); c.fillRect(w - 4 * u, 3 * u, u, u)
        c.fillRect(3 * u, h - 4 * u, u, u); c.fillRect(w - 4 * u, h - 4 * u, u, u)
      } else if (skinId === "circuit") {              // traces leaving the top and bottom edges
        c.fillStyle = Qt.rgba(ac.r, ac.g, ac.b, 0.7)
        var tx = Math.floor(w * 0.7 / u) * u
        c.fillRect(tx, u, u, 3 * u); c.fillRect(tx, 4 * u, 4 * u, u); c.fillRect(tx + 4 * u, 3 * u, 2 * u, 3 * u)
        var bx = Math.floor(w * 0.2 / u) * u
        c.fillRect(bx, h - 4 * u, u, 3 * u); c.fillRect(bx - 3 * u, h - 4 * u, 3 * u, u)
      } else if (skinId === "scanline") {             // faint scanlines across the fill
        c.fillStyle = Qt.rgba(ac.r, ac.g, ac.b, 0.07)
        for (var yy = 2 * u; yy < h - 2 * u; yy += 3 * u) c.fillRect(2 * u, yy, w - 4 * u, u)
      } else if (skinId === "neon") {                 // a second, glowing edge
        c.fillStyle = Qt.rgba(ac.r, ac.g, ac.b, 0.45)
        c.fillRect(s + u, u, w - 2 * s - 2 * u, u); c.fillRect(s + u, h - 2 * u, w - 2 * s - 2 * u, u)
        c.fillRect(u, s + u, u, h - 2 * s - 2 * u); c.fillRect(w - 2 * u, s + u, u, h - 2 * s - 2 * u)
      } else if (skinId === "glyph") {                // a small cross mark in the top-right corner
        c.fillStyle = ac
        c.fillRect(w - 5 * u, 2 * u, u, 3 * u); c.fillRect(w - 6 * u, 3 * u, 3 * u, u)
        c.fillRect(2 * u, h - 3 * u, 2 * u, u)
      }
    }
  }

  // A progress bar of separate blocks.
  component PixelBar: Canvas {
    id: pb
    property real frac: 0
    property int cells: 12
    property int cell: root.u
    property color on: root.accent
    property color off: root.faint
    height: 2 * cell
    onFracChanged: requestPaint()
    onOnChanged: requestPaint()
    onWidthChanged: requestPaint()
    onPaint: {
      var c = getContext("2d")
      c.reset()
      var gap = cell, bw = Math.max(cell, Math.floor((width - gap * (cells - 1)) / cells))
      var lit = Math.round(Math.max(0, Math.min(1, frac)) * cells)
      for (var i = 0; i < cells; i++) {
        c.fillStyle = i < lit ? on : off
        c.fillRect(i * (bw + gap), 0, bw, height)
      }
    }
  }

  // A stepped button: lifts one block on hover, fills with the accent when armed or selected.
  component PixelButton: Item {
    id: btn
    property string label: ""
    property string icon: ""
    property color iconTint: root.accent
    property bool selected: false
    property bool armed: false
    property bool enabled_: true
    property bool showLabel: true
    signal clicked()
    readonly property bool hot: hover.hovered && enabled_
    // with the label, whether or not it is shown (so a row can decide without a binding loop)
    readonly property real fullWidth: (icon ? 12 * root.u : 0) + (icon && label ? root.u * 2 : 0)
      + (label ? labelText.implicitWidth : 0) + root.u * 8
    readonly property real iconOnlyWidth: (icon ? 12 * root.u : labelText.implicitWidth) + root.u * 8
    implicitWidth: showLabel ? fullWidth : iconOnlyWidth
    implicitHeight: Math.max(44, labelText.implicitHeight + root.u * 6)
    opacity: enabled_ ? 1 : 0.45
    Accessible.role: Accessible.Button
    Accessible.name: label
    StepFrame {
      x: 0; y: root.u
      width: parent.width; height: parent.height - root.u
      fill: Qt.darker(root.well, 1.4)
      edge: "transparent"
      visible: btn.hot && !root.reduceMotion
    }
    StepFrame {
      id: face
      width: parent.width
      height: parent.height - root.u
      y: btn.hot && !root.reduceMotion ? 0 : root.u
      fill: btn.armed ? root.tint("red") : (btn.selected ? root.accent : (btn.hot ? root.raised : root.well))
      edge: btn.selected || btn.armed ? fill : (btn.hot ? root.accent : root.faint)
      Row {
        anchors.centerIn: parent
        spacing: root.u * 2
        PixelArt {
          visible: btn.icon !== ""
          anchors.verticalCenter: parent.verticalCenter
          name: btn.icon
          cell: root.u
          // on a filled (accent) face: dark outline, light fill, so the icon still reads
          tint: btn.selected || btn.armed ? Qt.lighter(btn.armed ? root.tint("red") : root.accent, 1.45) : btn.iconTint
          ink: btn.selected || btn.armed ? root.bg : root.fg
          hi: btn.selected || btn.armed ? root.fg : root.accent
        }
        Text {
          id: labelText
          visible: btn.showLabel && btn.label !== ""
          anchors.verticalCenter: parent.verticalCenter
          text: btn.armed ? "Again to confirm" : btn.label
          textFormat: Text.PlainText
          color: btn.selected || btn.armed ? root.bg : (btn.hot ? root.accent : root.fg)
          font.family: root.font
          font.pixelSize: Style.font.body
          font.bold: btn.selected
        }
      }
    }
    HoverHandler { id: hover; cursorShape: btn.enabled_ ? Qt.PointingHandCursor : Qt.ArrowCursor }
    TapHandler { enabled: btn.enabled_; onTapped: btn.clicked() }
  }

  component Caption: Text {
    color: root.dim
    font.family: root.font
    font.pixelSize: Style.font.bodySmall
    wrapMode: Text.WordWrap
    textFormat: Text.PlainText
  }
  component Body: Text {
    color: root.fg
    font.family: root.font
    font.pixelSize: Style.font.body
    wrapMode: Text.WordWrap
    textFormat: Text.PlainText
  }
  // A six-axis hexagon of the area levels: the shape of your Rice rating.
  component RiceHex: Canvas {
    id: hex
    property var areas: root.rice.areas || []
    width: 56 * root.u
    height: 56 * root.u
    onAreasChanged: requestPaint()
    onPaint: {
      var c = getContext("2d")
      c.reset()
      var cx = width / 2, cy = height / 2, r = width / 2 - root.u * 2
      function pt(i, f) { var a = -Math.PI / 2 + i * Math.PI / 3; return [cx + Math.cos(a) * r * f, cy + Math.sin(a) * r * f] }
      c.lineWidth = Math.max(1, root.u / 2)
      c.strokeStyle = root.faint
      for (var ring = 1; ring <= 4; ring++) {
        c.beginPath()
        for (var i = 0; i < 6; i++) { var p = pt(i, ring / 4); if (i === 0) c.moveTo(p[0], p[1]); else c.lineTo(p[0], p[1]) }
        c.closePath(); c.stroke()
      }
      if (areas.length < 6) return
      c.beginPath()
      for (var j = 0; j < 6; j++) { var q = pt(j, Math.max(0.04, areas[j].level / 100)); if (j === 0) c.moveTo(q[0], q[1]); else c.lineTo(q[0], q[1]) }
      c.closePath()
      c.fillStyle = Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.45)
      c.fill()
      c.strokeStyle = root.accent
      c.stroke()
      for (var k = 0; k < 6; k++) {
        var v = pt(k, Math.max(0.04, areas[k].level / 100))
        c.fillStyle = root.tint(areas[k].tint)
        c.fillRect(Math.round(v[0] - root.u), Math.round(v[1] - root.u), root.u * 2, root.u * 2)
      }
    }
  }

  // A section heading: icon + pixel-face title.
  component Heading: Row {
    property string icon: ""
    property string text: ""
    property color iconTint: root.accent
    spacing: root.u * 2
    PixelArt { visible: parent.icon !== ""; name: parent.icon; tint: parent.iconTint; cell: root.u; anchors.verticalCenter: parent.verticalCenter }
    PixelText { text: parent.text; cell: root.u; color: root.accent; anchors.verticalCenter: parent.verticalCenter }
  }
  // A framed card that sizes to its content.
  component Card: StepFrame {
    decor: true
    default property alias content: inner.data
    property int pad: root.u * 4
    width: parent ? parent.width : 0
    height: inner.implicitHeight + pad * 2
    Column {
      id: inner
      x: parent.pad; y: parent.pad
      width: parent.width - parent.pad * 2
      spacing: root.u * 3
    }
  }

  // ---- bar button ------------------------------------------------------------------
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    labelVisible: false
    hasVisualContent: true
    fixedWidth: vertical ? -1 : readout.implicitWidth + Style.space(12)
    fixedHeight: vertical ? readout.implicitHeight + Style.space(8) : -1
    tooltipText: "OmaLvL  ·  Rice " + root.rice.rating + " (" + root.rice.rank + ")"
      + "\nTotal level " + root.total + " / " + (root.sk.maxTotal || 1700) + "  ·  renown " + root.qp + " / " + root.maxQp
      + (root.contract.task ? "\nContract: " + root.contract.task.text + " (" + root.contract.task.done + "/" + root.contract.task.n + ")" : "")
      + (root.signal ? "\nSignal: " + root.signal.hint : "")
      + (root.tokens ? "\n" + root.tokens + " XP token" + (root.tokens > 1 ? "s" : "") + " to spend" : "")
      + (root.surge ? "\nOverclock: " + root.surge.name + " XP ×2" : "")
      + (root.season.updateDay ? "\nUpdate Day: System XP +" + root.season.updateDay.bonus + "%" : "")
      + (root.sysop && !root.sysop.done ? "\nSysop: " + root.sysop.task : "")
      + (root.ripe ? "\nJobs: " + root.ripe + " ready to collect" : "")
      + "\nClick for skills, quests and tasks"
    onPressed: function(b) { root.toggle() }
    Row {
      id: readout
      anchors.centerIn: parent
      spacing: Style.space(5)
      readonly property color ink: root.bar ? root.bar.foreground : root.fg
      PixelArt {
        anchors.verticalCenter: parent.verticalCenter
        name: "total"
        cell: Math.max(1, Math.floor(Style.font.body * 1.2 / 12))
        ink: readout.ink
        tint: root.accent
        hi: root.tint("yellow")
      }
      Text {
        anchors.verticalCenter: parent.verticalCenter
        text: root.total
        textFormat: Text.PlainText
        color: readout.ink
        font.family: root.bar ? root.bar.fontFamily : root.font
        font.pixelSize: Style.font.body
        font.bold: true
      }
      // Something waiting (token, signal, finished job, overclock): one accent block.
      Rectangle {
        visible: root.tokens > 0 || root.signal !== null || root.ripe > 0 || !!root.surge
        anchors.verticalCenter: parent.verticalCenter
        width: Math.max(3, Math.round(Style.font.body / 3)); height: width
        color: root.surge ? root.tint("yellow") : root.accent
      }
    }
  }

  // ---- XP drops: pixel numbers rise from the button in whole-block steps --------------
  PopupWindow {
    id: drops
    property var gains: []
    property var ups: []
    property int milestone: 0
    readonly property bool party: ups.length > 0 || milestone > 0
    function show(g, u, m) {
      drops.gains = (g || []).slice(0, 4)
      drops.ups = u || []
      drops.milestone = m || 0
      dropAnim.restart()
      if (drops.party) burst.restart()
    }
    visible: dropAnim.running || burst.running
    color: "transparent"
    implicitWidth: Style.space(300)
    implicitHeight: party ? Style.space(240) : Style.space(110)
    mask: Region {}
    anchor {
      window: button.QsWindow.window
      rect.width: 1
      rect.height: 1
      onAnchoring: {
        var w = button.QsWindow.window
        if (!w) return
        var p = w.contentItem.mapFromItem(button, button.width / 2 - drops.implicitWidth / 2, button.height + 2)
        drops.anchor.rect.x = Math.round(Math.max(0, Math.min(p.x, w.width - drops.implicitWidth)))
        drops.anchor.rect.y = Math.round(p.y)
      }
    }
    property real t: 0
    property real b: 0
    readonly property int step: root.u * 2
    // Level up: blocks fly out on a grid and fall, then a pixel banner.
    Item {
      anchors.fill: parent
      visible: drops.party
      Repeater {
        model: 28
        delegate: Rectangle {
          required property int index
          readonly property real a: index / 28 * Math.PI * 2
          readonly property real r: (index % 2 ? 0.65 : 1) * Style.space(110) * drops.b
          readonly property var tints: ["accent", "yellow", "green", "cyan", "magenta", "red", "orange"]
          width: root.u * (index % 3 === 0 ? 3 : 2); height: width
          color: tints[index % 7] === "accent" ? root.accent : root.tint(tints[index % 7])
          x: Math.round((drops.width / 2 + Math.cos(a) * r) / drops.step) * drops.step
          y: Math.round((Style.space(130) + Math.sin(a) * r + Style.space(50) * drops.b * drops.b) / drops.step) * drops.step
          opacity: drops.b > 0 ? Math.max(0, 1 - drops.b * drops.b * drops.b) : 0
        }
      }
      Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: Style.space(118)
        spacing: root.u * 2
        opacity: drops.b > 0 ? Math.min(1, 3 * (1 - drops.b)) : 0
        PixelText {
          anchors.horizontalCenter: parent.horizontalCenter
          cell: root.u * 2
          color: root.accent
          text: drops.milestone ? "Total " + drops.milestone : "Level up"
        }
        Repeater {
          model: drops.ups
          delegate: PixelText {
            required property var modelData
            anchors.horizontalCenter: parent ? parent.horizontalCenter : undefined
            cell: root.u
            color: root.fg
            text: root.nameOf(modelData[0]) + " " + modelData[modelData.length - 1]
          }
        }
      }
    }
    Column {
      id: dropCol
      anchors.horizontalCenter: parent.horizontalCenter
      spacing: root.u * 2
      y: Math.round(drops.t * Style.space(60) / drops.step) * drops.step
      opacity: 1 - Math.max(0, drops.t - 0.6) / 0.4
      Repeater {
        model: drops.gains
        delegate: Row {
          required property var modelData
          anchors.horizontalCenter: parent.horizontalCenter
          spacing: root.u * 2
          PixelArt {
            anchors.verticalCenter: parent.verticalCenter
            name: parent.modelData.skill
            cell: root.u
            tint: root.tint((root.skill(parent.modelData.skill) || {}).tint)
          }
          PixelText {
            anchors.verticalCenter: parent.verticalCenter
            cell: root.u
            color: root.fg
            text: "+" + parent.modelData.xp
          }
        }
      }
    }
    NumberAnimation { id: dropAnim; target: drops; property: "t"; from: 0; to: 1; duration: 1600 }
    NumberAnimation { id: burst; target: drops; property: "b"; from: 0; to: 1; duration: 1500; easing.type: Easing.OutQuad }
  }

  // ---- panel -------------------------------------------------------------------------
  // Layout metrics: six area cards in two columns, three skill rows each. The icon scale is the
  // largest whole number at which the Skills tab fits this screen's card.
  readonly property real chromeHeight: panel.verticalContentInset + tabRow.implicitHeight + header.implicitHeight
    + readoutCard.height + body.spacing * 3
  readonly property int tileGap: root.u * 2
  readonly property int iconCell: Math.max(2, Math.min(3, Math.floor(((panel.availableCardHeight || 860) - chromeHeight
    - 3 * (Style.font.body * 2 + root.u * 14)) / 9 / (12 + 4))))
  readonly property int tileHeight: 12 * iconCell + root.u * 3
  readonly property int gridWidth: Math.max(Style.space(600), 2 * (12 * iconCell + Style.font.body * 12) + tileGap)

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Math.max(root.gridWidth, tabRow.naturalWidth) + panel.padding * 2
      + Border.left(panel.borderSpec) + Border.right(panel.borderSpec))
    contentHeight: panel.fittedContentHeight(body.implicitHeight,
      root.tab === "skills" && root.guideSkill === "" ? 0 : Math.max(Style.space(780), 9 * root.tileHeight + root.chromeHeight))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onActivateRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      ScrollView {
        id: scroll
        anchors.fill: parent
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical.policy: body.implicitHeight > height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff

        Column {
          id: body
          width: scroll.availableWidth
          spacing: root.u * 4

          // tabs: labelled when they fit, icons only when they don't
          Row {
            id: tabRow
            width: parent.width
            spacing: root.u * 2
            readonly property var tabs: [
              { id: "skills", label: "Skills", icon: "total" }, { id: "rice", label: "Rice", icon: "rice" },
              { id: "quests", label: "Quests", icon: "quests" },
              { id: "tasks", label: "Tasks", icon: "tasks" }, { id: "diary", label: "Journal", icon: "diary" },
              { id: "collection", label: "Collection", icon: "collection" }, { id: "log", label: "Log", icon: "log" }]
            readonly property real naturalWidth: {
              var w = 0
              for (var i = 0; i < children.length; i++)
                if (children[i].fullWidth !== undefined) w += children[i].fullWidth
              return w + spacing * (tabs.length - 1)
            }
            readonly property bool compact: naturalWidth > width + 0.5
            readonly property real share: {
              var used = 0
              for (var i = 0; i < children.length; i++)
                if (children[i].fullWidth !== undefined) used += compact ? children[i].iconOnlyWidth : children[i].fullWidth
              return Math.max(0, Math.floor((width - used - spacing * (tabs.length - 1)) / tabs.length))
            }
            Repeater {
              model: tabRow.tabs
              delegate: PixelButton {
                required property var modelData
                label: modelData.label
                icon: modelData.icon
                showLabel: !tabRow.compact
                width: implicitWidth + tabRow.share
                selected: root.tab === modelData.id
                onClicked: root.tab = modelData.id
              }
            }
          }

          // header: pixel title left, the tab's big number right
          Item {
            id: header
            width: parent.width
            implicitHeight: Math.max(titleCol.implicitHeight, numCol.implicitHeight)
            Column {
              id: titleCol
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              spacing: root.u * 2
              PixelText {
                cell: root.u * 2
                color: root.fg
                text: ({ skills: "Skills", rice: "Rice", quests: "Quests", tasks: "Tasks", diary: "Journal",
                         collection: "Collection", log: "Activity" })[root.tab]
              }
              Caption {
                text: ({ skills: "Six areas, levelled by using this machine", rice: "Keybind tree, relics, seasons and skins",
                         quests: "Learn Omarchy, Linux and AI by doing it",
                         tasks: "Contracts, signals, tokens and the Sysop", diary: "Boot, Login, Root, Kernel: a token each",
                         collection: "Companions, mastery marks and finds", log: "What earned XP, and why" })[root.tab]
              }
            }
            Column {
              id: numCol
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: root.u * 2
              PixelText {
                anchors.right: parent.right
                cell: root.u * 2
                color: root.accent
                text: root.tab === "quests" ? root.qp + "/" + root.maxQp
                  : (root.tab === "tasks" ? (root.contract.points || 0) + " pts"
                     : (root.tab === "rice" ? "Rice " + root.rice.rating : root.total + "/" + (root.sk.maxTotal || 1700)))
              }
              Caption {
                anchors.right: parent.right
                text: root.tab === "quests" ? "renown"
                  : (root.tab === "tasks" ? "contract points  ·  streak " + (root.contract.streak || 0)
                     : (root.tab === "rice" ? root.rice.rank
                        : "total level  ·  Rice " + root.rice.rating
                          + (root.sk.xpRate ? "  ·  " + root.n(root.sk.xpRate) + " xp/hr" : "")))
              }
            }
          }

          // ---- skills: six area cards --------------------------------------------
          Grid {
            id: grid
            visible: root.tab === "skills" && root.guideSkill === ""
            width: parent.width
            columns: 2
            spacing: root.tileGap
            Repeater {
              model: root.rice.areas || []
              delegate: StepFrame {
                id: areaCard
                required property var modelData
                readonly property color tintA: root.tint(modelData.tint)
                decor: true
                width: (grid.width - grid.spacing) / 2
                height: areaCol.implicitHeight + root.u * 6
                Column {
                  id: areaCol
                  x: root.u * 3; y: root.u * 3
                  width: parent.width - root.u * 6
                  spacing: root.u
                  Item {
                    width: parent.width
                    height: areaTitle.height + root.u * 2
                    PixelText { id: areaTitle; cell: root.u; text: areaCard.modelData.name; color: areaCard.tintA }
                    Caption {
                      anchors.right: parent.right
                      anchors.verticalCenter: areaTitle.verticalCenter
                      text: "area " + Math.floor(areaCard.modelData.level)
                    }
                  }
                  Repeater {
                    model: root.skillsOf(areaCard.modelData.id)
                    delegate: Item {
                      id: tile
                      required property var modelData
                      readonly property bool hot: tileHover.hovered
                      readonly property color tintC: root.tint(modelData.tint)
                      readonly property bool surged: !!root.surge && root.surge.skill === modelData.key
                      width: areaCol.width
                      height: root.tileHeight
                      Accessible.role: Accessible.Button
                      Accessible.name: modelData.name + ", level " + modelData.level
                      Rectangle {
                        anchors.fill: parent
                        color: tile.hot ? root.raised : "transparent"
                        border.width: tile.surged ? root.u : 0
                        border.color: root.tint("yellow")
                      }
                      PixelArt {
                        id: tileIcon
                        x: root.u
                        anchors.verticalCenter: parent.verticalCenter
                        name: tile.modelData.key
                        cell: root.iconCell
                        tint: tile.tintC
                      }
                      Column {
                        anchors.left: tileIcon.right
                        anchors.leftMargin: root.u * 3
                        anchors.right: parent.right
                        anchors.rightMargin: root.u * 2
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: root.u * 2
                        Row {
                          spacing: root.u * 2
                          PixelText { cell: root.u * (root.iconCell >= 3 ? 2 : 1); color: tile.modelData.mastered ? root.accent : root.fg; text: tile.modelData.level }
                          Text {
                            anchors.bottom: parent.bottom
                            text: tile.modelData.name
                            textFormat: Text.PlainText
                            color: root.dim
                            font.family: root.font
                            font.pixelSize: Style.font.bodySmall
                            elide: Text.ElideRight
                          }
                        }
                        PixelBar {
                          width: parent.width
                          cells: 10
                          on: tile.tintC
                          frac: tile.modelData.span ? 1 - tile.modelData.toNext / tile.modelData.span : 1
                        }
                      }
                      HoverHandler {
                        id: tileHover
                        cursorShape: Qt.PointingHandCursor
                        onHoveredChanged: if (hovered) root.hoverSkill = tile.modelData.key
                                          else if (root.hoverSkill === tile.modelData.key) root.hoverSkill = ""
                      }
                      TapHandler { onTapped: root.guideSkill = tile.modelData.key }
                    }
                  }
                }
              }
            }
          }

          // the readout under the areas: hovered skill, or the Rice rating
          Card {
            id: readoutCard
            visible: root.tab === "skills" && root.guideSkill === ""
            readonly property var s: root.hoverSkill ? root.skill(root.hoverSkill) : null
            Row {
              spacing: root.u * 4
              width: parent.width
              RiceHex { id: hexView; anchors.verticalCenter: parent.verticalCenter }
              Column {
                width: parent.width - hexView.width - root.u * 4
                anchors.verticalCenter: parent.verticalCenter
                spacing: root.u * 2
                Row {
                  spacing: root.u * 2
                  PixelArt {
                    anchors.verticalCenter: parent.verticalCenter
                    name: readoutCard.s ? readoutCard.s.key : "rice"
                    cell: root.u * 2
                    tint: readoutCard.s ? root.tint(readoutCard.s.tint) : root.accent
                  }
                  PixelText {
                    anchors.verticalCenter: parent.verticalCenter
                    cell: root.u * 2
                    color: root.fg
                    text: readoutCard.s ? readoutCard.s.name + " " + readoutCard.s.level : "Rice " + root.rice.rating
                  }
                }
                Body {
                  width: parent.width
                  font.bold: true
                  text: readoutCard.s ? root.n(readoutCard.s.xp) + " XP"
                      + (readoutCard.s.level < root.maxLevel ? "  ·  " + root.n(readoutCard.s.toNext) + " to " + (readoutCard.s.level + 1) : "  ·  mastered")
                    : root.rice.rank + (root.rice.next ? "  ·  " + root.rice.next.rank + " at " + root.rice.next.rating : "")
                }
                Caption {
                  width: parent.width
                  text: readoutCard.s
                    ? (readoutCard.s.eta ? "About " + root.dur(readoutCard.s.eta) + " to the next level.  " : "")
                      + "Trains on: " + readoutCard.s.blurb + ".  Click for its guide."
                    : (root.rice.weakest ? "Weakest area: " + root.rice.weakest.area + ". Train " + root.rice.weakest.name + " to lift it.  " : "")
                      + (root.season.areaName ? "Season: " + root.season.theme + " boosts " + root.season.areaName + " +" + root.season.bonus + "%." : "")
                }
              }
            }
          }

          // ---- rice: keybind tree, relics, season and stamps, skins -------------------
          Column {
            visible: root.tab === "rice"
            width: parent.width
            spacing: root.u * 3
            Card {
              Row {
                spacing: root.u * 4
                width: parent.width
                RiceHex { id: hexBig; anchors.verticalCenter: parent.verticalCenter }
                Column {
                  width: parent.width - hexBig.width - root.u * 4
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: root.u * 2
                  Repeater {
                    model: root.rice.areas || []
                    delegate: Row {
                      required property var modelData
                      width: parent.width
                      spacing: root.u * 2
                      Body { width: Style.font.body * 6; text: parent.modelData.name; color: root.tint(parent.modelData.tint) }
                      PixelBar { anchors.verticalCenter: parent.verticalCenter; width: parent.width - Style.font.body * 9; cells: 20; on: root.tint(parent.modelData.tint); frac: parent.modelData.level / 100 }
                      Caption { text: Math.floor(parent.modelData.level) }
                    }
                  }
                  Caption {
                    width: parent.width
                    text: "Rice rating = 10 x the mean of the six area levels. " + (root.rice.next ? root.rice.next.rank + " at " + root.rice.next.rating + "." : "Top rank.")
                  }
                }
              }
            }
            Card {
              Heading { icon: "season"; text: "Season"; iconTint: root.tint("green") }
              Body {
                width: parent.width
                text: root.season.theme ? "Wearing " + root.season.theme + ": " + root.season.areaName + " XP +" + root.season.bonus + "%."
                  + (root.season.stamps && root.season.stamps.some(function(st) { return st.theme === root.season.theme }) ? "  Stamped."
                     : "  " + (root.season.wearing || 0) + " / " + (root.season.stampMinutes || 30) + " minutes to its stamp.")
                  : "No Omarchy theme found."
              }
              Body {
                visible: !!root.season.updateDay
                width: parent.width
                text: root.season.updateDay ? "Update Day: System XP +" + root.season.updateDay.bonus + "% for " + root.dur(root.season.updateDay.until - root.nowS) + " more." : ""
              }
              Caption {
                width: parent.width
                text: "Every theme favours one area. Wear a theme for " + (root.season.stampMinutes || 30) + " active minutes to stamp it. Run omarchy update for Update Day."
              }
              Flow {
                width: parent.width
                spacing: root.u * 2
                Repeater {
                  model: root.season.stamps || []
                  delegate: Row {
                    required property var modelData
                    spacing: root.u
                    PixelArt { name: "stamp"; cell: root.u; tint: root.accent; anchors.verticalCenter: parent.verticalCenter }
                    Caption { text: parent.modelData.theme; anchors.verticalCenter: parent.verticalCenter }
                  }
                }
              }
            }
            Card {
              Heading { icon: "tree"; text: "Keybind tree" }
              Caption { width: parent.width; text: "Every Omarchy action you use ranks up: learned at 1 use, practised at 10, mastered at 50." }
              Repeater {
                model: root.tree
                delegate: Column {
                  id: branch
                  required property var modelData
                  width: parent.width
                  spacing: root.u
                  Body { text: branch.modelData.name + "  ·  " + branch.modelData.found + " found, " + branch.modelData.mastered + " mastered"; font.bold: true }
                  Flow {
                    width: parent.width
                    spacing: root.u * 2
                    Repeater {
                      model: branch.modelData.nodes
                      delegate: StepFrame {
                        required property var modelData
                        width: nodeText.implicitWidth + root.u * 6
                        height: nodeText.implicitHeight + root.u * 3
                        fill: modelData.rank >= 3 ? root.accent : (modelData.rank ? root.raised : root.well)
                        edge: modelData.rank ? root.accent : root.faint
                        Caption {
                          id: nodeText
                          anchors.centerIn: parent
                          color: parent.modelData.rank >= 3 ? root.bg : (parent.modelData.rank ? root.fg : root.dim)
                          text: parent.modelData.name + (parent.modelData.uses ? " " + parent.modelData.uses : "")
                        }
                      }
                    }
                  }
                }
              }
            }
            Card {
              Heading { icon: "relic"; text: "Dotfile relics  " + root.relics.filter(function(r) { return r.found }).length + "/" + root.relics.length }
              Caption { width: parent.width; text: "Commit your config (hypr, nvim, colours, shell, git ...) in a watched repo to unearth its relic." }
              Flow {
                width: parent.width
                spacing: root.u * 3
                Repeater {
                  model: root.relics
                  delegate: Row {
                    required property var modelData
                    spacing: root.u
                    PixelArt { name: "relic"; cell: root.u; ghost: !parent.modelData.found; tint: root.tint("yellow"); anchors.verticalCenter: parent.verticalCenter }
                    Caption { text: parent.modelData.name; color: parent.modelData.found ? root.fg : root.dim; anchors.verticalCenter: parent.verticalCenter }
                  }
                }
              }
            }
            Card {
              Heading { icon: "skin"; text: "Skins" }
              Caption { width: parent.width; text: "Frames for this panel, unlocked by your Rice rating." }
              Flow {
                width: parent.width
                spacing: root.u * 2
                Repeater {
                  model: root.skins
                  delegate: PixelButton {
                    required property var modelData
                    label: modelData.name + (modelData.unlocked ? "" : " " + modelData.need)
                    icon: modelData.unlocked ? "skin" : "lock"
                    selected: modelData.worn
                    enabled_: modelData.unlocked && root.busy === ""
                    onClicked: root.run(["skin", modelData.id])
                  }
                }
              }
            }
          }

          // ---- skill guide ----          // ---- skill guide ----------------------------------------------------------
          Column {
            id: guideView
            visible: root.tab === "skills" && root.guideSkill !== ""
            width: parent.width
            spacing: root.u * 4
            readonly property var s: root.guideSkill ? root.skill(root.guideSkill) : null
            readonly property var g: root.guide
            Row {
              spacing: root.u * 4
              PixelArt {
                name: root.guideSkill
                cell: root.u * 3
                tint: guideView.s ? root.tint(guideView.s.tint) : root.accent
              }
              Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: root.u * 2
                PixelText { cell: root.u * 2; text: guideView.s ? guideView.s.name : ""; color: root.fg }
                Body {
                  text: guideView.s ? "Level " + guideView.s.level + "  ·  " + root.n(guideView.s.xp) + " XP"
                    + (guideView.s.level < root.maxLevel ? "  ·  " + root.n(guideView.s.toNext) + " to " + (guideView.s.level + 1) : "  ·  mastered") : ""
                }
                Caption {
                  text: guideView.g ? (guideView.g.rate ? root.n(guideView.g.rate) + " XP/hr lately" : "No recent XP")
                    + "  ·  " + root.n(guideView.g.toMax) + " XP to 100  ·  " + guideView.g.area : "Loading..."
                }
              }
            }
            PixelBar {
              width: parent.width
              cells: 24
              on: guideView.s ? root.tint(guideView.s.tint) : root.accent
              frac: guideView.s && guideView.s.span ? 1 - guideView.s.toNext / guideView.s.span : 1
            }
            Card {
              visible: !!guideView.g
              Heading { icon: "tasks"; text: "How to train" }
              Repeater {
                model: root.guide ? root.guide.training : []
                delegate: Row {
                  required property var modelData
                  width: parent.width
                  Body { width: parent.width * 0.62; text: parent.modelData.what }
                  Caption { width: parent.width * 0.38; horizontalAlignment: Text.AlignRight; text: parent.modelData.xp }
                }
              }
            }
            Card {
              visible: !!guideView.g && !!root.guide.unlocks && root.guide.unlocks.length > 0
              Heading { icon: "quests"; text: "Unlocks" }
              Repeater {
                model: root.guide ? root.guide.unlocks : []
                delegate: Row {
                  required property var modelData
                  width: parent.width
                  spacing: root.u * 3
                  PixelArt { name: parent.modelData.met ? "check" : "lock"; cell: Math.max(1, Math.round(root.u * 1.5)); tint: root.tint("green"); anchors.verticalCenter: parent.verticalCenter }
                  PixelText { cell: root.u; text: parent.modelData.level; color: parent.modelData.met ? root.accent : root.dim; anchors.verticalCenter: parent.verticalCenter }
                  Body { width: parent.width - 30 * root.u; text: parent.modelData.text; color: parent.modelData.met ? root.fg : root.dim }
                }
              }
            }
            Row {
              spacing: root.u * 3
              PixelButton { label: "Back"; icon: "total"; onClicked: root.guideSkill = "" }
              PixelButton {
                visible: root.tokens > 0
                label: "Redeem a token here"
                icon: "token"
                armed: root.confirmKey === "token:" + root.guideSkill
                onClicked: root.twoClick("token:" + root.guideSkill, ["token", root.guideSkill])
              }
            }
          }

          // ---- quests ------------------------------------------------------------
          Column {
            visible: root.tab === "quests"
            width: parent.width
            spacing: root.u * 2
            Repeater {
              model: root.quests
              delegate: StepFrame {
                id: qrow
                required property var modelData
                readonly property bool open: root.expandedQuest === modelData.id
                readonly property bool hot: qHover.hovered
                width: parent.width
                height: qcol.implicitHeight + root.u * 6
                fill: hot || open ? root.raised : root.well
                edge: open ? root.accent : root.faint
                Column {
                  id: qcol
                  x: root.u * 4; y: root.u * 3
                  width: parent.width - root.u * 8
                  spacing: root.u * 2
                  Item {
                    width: parent.width
                    height: Math.max(44 - root.u * 6, qname.implicitHeight)
                    PixelArt {
                      id: qicon
                      anchors.verticalCenter: parent.verticalCenter
                      name: qrow.modelData.done ? "check" : (qrow.modelData.locked ? "lock" : "quests")
                      cell: Math.max(1, Math.round(root.u * 1.5))
                      tint: qrow.modelData.done ? root.tint("green") : root.accent
                    }
                    Body {
                      id: qname
                      anchors.left: qicon.right; anchors.leftMargin: root.u * 3
                      anchors.right: qmeta.left; anchors.rightMargin: root.u * 3
                      anchors.verticalCenter: parent.verticalCenter
                      text: qrow.modelData.name
                      color: qrow.modelData.done ? root.dim : root.fg
                      elide: Text.ElideRight
                      wrapMode: Text.NoWrap
                    }
                    Caption {
                      id: qmeta
                      anchors.right: parent.right
                      anchors.verticalCenter: parent.verticalCenter
                      wrapMode: Text.NoWrap
                      text: (qrow.modelData.auto ? "auto  ·  " : "") + qrow.modelData.qp + " renown"
                    }
                    HoverHandler { id: qHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: root.expandedQuest = qrow.open ? "" : qrow.modelData.id }
                  }
                  Column {
                    visible: qrow.open
                    width: parent.width
                    spacing: root.u * 2
                    Body { width: parent.width; text: qrow.modelData.desc }
                    Repeater {
                      model: qrow.modelData.steps
                      delegate: Row {
                        required property var modelData
                        width: parent.width
                        spacing: root.u * 3
                        Rectangle {
                          anchors.verticalCenter: parent.verticalCenter
                          width: root.u * 4; height: width
                          color: parent.modelData.done ? root.tint("green") : "transparent"
                          border.color: parent.modelData.done ? root.tint("green") : root.dim
                          border.width: root.u
                        }
                        Body {
                          width: parent.width - root.u * 7
                          text: parent.modelData.text + (parent.modelData.tracked ? "" : "  (tick by hand)")
                          color: parent.modelData.done ? root.dim : root.fg
                        }
                      }
                    }
                    Caption {
                      width: parent.width
                      text: "Reward: " + qrow.modelData.reward + "  ·  " + qrow.modelData.qp + " renown"
                        + (qrow.modelData.reqs.length ? "  ·  needs " + qrow.modelData.reqs.map(function(r) { return r.name + " " + r.level + (r.met ? " (met)" : "") }).join(", ") : "")
                    }
                    PixelButton {
                      visible: !qrow.modelData.done && !qrow.modelData.locked
                      label: "Mark complete"
                      icon: "check"
                      iconTint: root.tint("green")
                      armed: root.confirmKey === "quest:" + qrow.modelData.id
                      onClicked: root.twoClick("quest:" + qrow.modelData.id, ["quest", qrow.modelData.id])
                    }
                  }
                }
              }
            }
          }

          // ---- tasks -----------------------------------------------------------------
          Column {
            visible: root.tab === "tasks"
            width: parent.width
            spacing: root.u * 3
            Card {
              Heading { icon: "contracts"; text: "Dispatcher"; iconTint: root.tint("red") }
              Body {
                width: parent.width
                text: root.contract.task ? root.contract.task.text : (root.contract.canNew ? "No contract. Take one." : "No more contracts today.")
              }
              PixelBar {
                visible: !!root.contract.task
                width: parent.width
                cells: Math.max(1, Math.min(20, root.contract.task ? root.contract.task.n : 1))
                on: root.tint("red")
                frac: root.contract.task ? root.contract.task.done / root.contract.task.n : 0
              }
              Caption {
                text: (root.contract.task ? root.contract.task.done + " / " + root.contract.task.n + "  ·  " : "")
                  + "streak " + (root.contract.streak || 0) + "  ·  " + (root.contract.completed || 0) + " done"
              }
              Row {
                spacing: root.u * 3
                PixelButton {
                  visible: !root.contract.task && !!root.contract.canNew
                  label: "New contract"
                  onClicked: root.run(["contract", "new"])
                }
                PixelButton {
                  visible: !!root.contract.task
                  label: "Skip (resets streak)"
                  armed: root.confirmKey === "contract:skip"
                  onClicked: root.twoClick("contract:skip", ["contract", "skip"])
                }
              }
            }
            Card {
              Heading { icon: "signal"; text: "Signal"; iconTint: root.tint("cyan") }
              Body {
                width: parent.width
                text: root.signal ? root.signal.hint : "No signal. Random events and contracts send them."
              }
              Caption { visible: !!root.signal; text: root.signal ? root.signal.tier + "  ·  step " + root.signal.step + " of " + root.signal.steps : "" }
            }
            Card {
              Heading { icon: "token"; text: "XP tokens" }
              Body {
                width: parent.width
                text: root.tokens ? root.tokens + " token" + (root.tokens > 1 ? "s" : "") + " to redeem. Open a skill's guide and redeem it there."
                                  : "No tokens. Couriers, signal caches, journal tiers and Update Day give them."
              }
            }
            Card {
              Heading { icon: "sysop"; text: "The Sysop"; iconTint: root.tint("magenta") }
              Body { width: parent.width; text: root.sysop ? root.sysop.task + (root.sysop.done ? "  (done)" : "") : "The Sysop is setting today's challenge. Use the machine for a minute." }
              Text {
                visible: !!root.sysop
                width: parent.width
                text: root.sysop ? root.sysop.hint : ""
                color: root.accent
                font.family: "monospace"
                font.pixelSize: Style.font.body
                wrapMode: Text.WrapAnywhere
                textFormat: Text.PlainText
              }
              Caption { visible: !!root.sysop; width: parent.width; text: root.sysop ? "Reward: " + root.sysop.reward : "" }
              Caption { visible: !!root.sysop && root.sysop.explain !== ""; width: parent.width; text: root.sysop ? root.sysop.explain : "" }
              PixelButton {
                visible: !!root.sysop && root.sysop.explain === ""
                label: root.busy === "sysop explain" ? "Asking..." : "Explain it (local AI)"
                enabled_: root.busy === ""
                onClicked: root.run(["sysop", "explain"])
              }
            }
            Card {
              visible: !!root.surge || !!root.season.updateDay || (root.streak.count || 0) > 0
              Heading { icon: "overclock"; text: "Bonuses"; iconTint: root.tint("yellow") }
              Body {
                visible: !!root.surge
                width: parent.width
                text: root.surge ? "Overclock: " + root.surge.name + " XP is doubled for " + Math.max(1, Math.ceil((root.surge.until - root.nowS) / 60)) + " more minutes." : ""
              }
              Body {
                visible: (root.streak.count || 0) > 0
                width: parent.width
                text: "Daily streak: " + (root.streak.count || 0) + " day" + (root.streak.count === 1 ? "" : "s") + "  ·  best " + (root.streak.best || 0)
              }
              Body {
                visible: !!root.season.updateDay
                width: parent.width
                text: root.season.updateDay ? "Update Day: System XP +" + root.season.updateDay.bonus + "%." : ""
              }
            }
            Card {
              Heading { icon: "job_growing"; text: "Job slots"; iconTint: root.tint("green") }
              Caption { width: parent.width; text: "Queue a long job: omalvl run make -j4  ·  collect it when it's done for Workload XP." }
              Grid {
                columns: 4
                spacing: root.u * 3
                width: parent.width
                Repeater {
                  model: ["Alpha", "Bravo", "Charlie", "Delta"]
                  delegate: Column {
                    required property string modelData
                    readonly property var job: root.jobs.find(function(p) { return p.slot === modelData }) || null
                    width: (parent.width - 3 * root.u * 3) / 4
                    spacing: root.u
                    PixelArt {
                      anchors.horizontalCenter: parent.horizontalCenter
                      name: !parent.job ? "job_empty" : (parent.job.dead ? "job_dead" : (parent.job.done ? "job_done" : "job_growing"))
                      cell: root.u * 2
                      tint: root.tint("green")
                      hi: root.tint("yellow")
                    }
                    Caption { anchors.horizontalCenter: parent.horizontalCenter; text: parent.modelData }
                    Caption {
                      width: parent.width
                      horizontalAlignment: Text.AlignHCenter
                      elide: Text.ElideRight
                      wrapMode: Text.NoWrap
                      text: parent.job ? parent.job.cmd : "empty"
                    }
                  }
                }
              }
              PixelButton {
                visible: root.ripe > 0
                label: "Collect " + root.ripe
                icon: "job_done"
                onClicked: root.run(["collect"])
              }
            }
          }

          // ---- journal (diary) ---------------------------------------------------------
          Column {
            visible: root.tab === "diary"
            width: parent.width
            spacing: root.u * 3
            Repeater {
              model: root.diary
              delegate: Card {
                id: tier
                required property var modelData
                readonly property int doneCount: modelData.tasks.filter(function(t) { return t.done }).length
                Row {
                  width: parent.width
                  spacing: root.u * 3
                  PixelArt { name: tier.modelData.done ? "check" : "diary"; cell: root.u; tint: tier.modelData.done ? root.tint("green") : root.accent; anchors.verticalCenter: parent.verticalCenter }
                  PixelText { cell: root.u; text: tier.modelData.title; color: tier.modelData.done ? root.tint("green") : root.accent; anchors.verticalCenter: parent.verticalCenter }
                  Caption { anchors.verticalCenter: parent.verticalCenter; text: tier.doneCount + " / " + tier.modelData.tasks.length + "  ·  reward: " + root.n(tier.modelData.token) + " XP token" }
                }
                PixelBar { width: parent.width; cells: tier.modelData.tasks.length; on: root.tint("green"); frac: tier.doneCount / Math.max(1, tier.modelData.tasks.length) }
                Repeater {
                  model: tier.modelData.tasks
                  delegate: Row {
                    required property var modelData
                    width: parent.width
                    spacing: root.u * 3
                    Rectangle {
                      anchors.verticalCenter: parent.verticalCenter
                      width: root.u * 4; height: width
                      color: parent.modelData.done ? root.tint("green") : "transparent"
                      border.color: parent.modelData.done ? root.tint("green") : root.dim
                      border.width: root.u
                    }
                    Body {
                      width: parent.width - root.u * 7
                      text: parent.modelData.text + (parent.modelData.need > 1 && !parent.modelData.done ? "  (" + root.n(parent.modelData.have) + " / " + root.n(parent.modelData.need) + ")" : "")
                      color: parent.modelData.done ? root.dim : root.fg
                    }
                  }
                }
              }
            }
          }

          // ---- collection ---------------------------------------------------------------
          Column {
            visible: root.tab === "collection"
            width: parent.width
            spacing: root.u * 3
            Card {
              Heading { icon: "collection"; text: "Companions  " + root.companions.filter(function(c) { return c.owned }).length + "/" + root.companions.length }
              Caption { width: parent.width; text: "Each companion hatches when its skill reaches a set level. No luck involved." }
              Grid {
                columns: Math.max(3, Math.floor(parent.width / (16 * root.u * 2)))
                spacing: root.u * 3
                Repeater {
                  model: root.companions
                  delegate: Column {
                    required property var modelData
                    width: 14 * root.u * 2
                    spacing: root.u
                    PixelArt {
                      anchors.horizontalCenter: parent.horizontalCenter
                      name: parent.modelData.id
                      cell: root.u * 2
                      ghost: !parent.modelData.owned
                      tint: root.tint((root.skill(parent.modelData.skill) || {}).tint)
                    }
                    Caption {
                      width: parent.width
                      horizontalAlignment: Text.AlignHCenter
                      text: parent.modelData.owned ? parent.modelData.name : parent.modelData.skillName + " " + parent.modelData.level
                    }
                  }
                }
              }
            }
            Card {
              Heading { icon: "mark"; text: "Mastery marks  " + Object.keys(root.marks).filter(function(k) { return k !== "max" && k !== "questmaster" }).length + "/" + root.skills.length }
              Caption { width: parent.width; text: "Level 100 earns that skill's mark; every quest earns Questmaster; every skill at 100 earns Omarchist." }
              Flow {
                width: parent.width
                spacing: root.u * 2
                Repeater {
                  model: root.skills
                  delegate: PixelArt {
                    required property var modelData
                    name: "mark"
                    cell: root.u * 2
                    ghost: !root.marks[modelData.key]
                    tint: root.tint(modelData.tint)
                    ToolTip.visible: badgeHover.hovered
                    ToolTip.text: modelData.name + (root.marks[modelData.key] ? " mastery mark" : ": reach 100")
                    HoverHandler { id: badgeHover }
                  }
                }
              }
            }
            Card {
              Heading { icon: "token"; text: "Finds" }
              Repeater {
                model: [["Signal caches", "cache:"], ["Random events", "random:"], ["Overclocks", "surge"],
                        ["Update Days", "update_day"], ["Sysop challenges", "sysop"], ["Milestones", "milestone:"]]
                delegate: Row {
                  required property var modelData
                  width: parent.width
                  readonly property int count: {
                    var t = 0
                    for (var k in root.coll) if (k === modelData[1] || k.indexOf(modelData[1]) === 0) t += root.coll[k]
                    return t
                  }
                  Body { width: parent.width * 0.7; text: parent.modelData[0] }
                  PixelText { cell: root.u; text: parent.count; color: parent.count ? root.accent : root.dim }
                }
              }
            }
          }

          // ---- log ------------------------------------------------------------------------
          Column {
            visible: root.tab === "log"
            width: parent.width
            spacing: root.u * 2
            Card {
              id: fairCard
              readonly property var fp: root.sk.fairPlay || ({ verified: true, voided: 0 })
              edge: fp.verified ? root.faint : root.tint("red")
              Row {
                spacing: root.u * 3
                PixelArt { name: fairCard.fp.verified ? "check" : "lock"; cell: root.u; tint: fairCard.fp.verified ? root.tint("green") : root.tint("red"); anchors.verticalCenter: parent.verticalCenter }
                PixelText { cell: root.u; text: fairCard.fp.verified ? "Fair play" : "Unverified"; color: fairCard.fp.verified ? root.accent : root.tint("red"); anchors.verticalCenter: parent.verticalCenter }
              }
              Caption {
                width: parent.width
                readonly property var fp: fairCard.fp
                text: (fp.verified ? "Every XP is accounted for." : "Edited by hand: " + (fp.unverified || []).join(", ") + ".")
                  + "  ·  " + (fp.voided || 0) + " voided award" + (fp.voided === 1 ? "" : "s")
                  + "  ·  award budget left today: " + root.n(fp.budgetLeft) + " XP"
                  + (fp.adminGrants ? "  ·  admin grants: " + fp.adminGrants + " (" + root.n(fp.adminXp) + " XP)" : "")
                  + (fp.hold ? "  ·  measured XP is on hold: activity around the clock" : "")
              }
            }
            Repeater {
              model: root.activity.slice().reverse()
              delegate: StepFrame {
                id: logRow
                required property var modelData
                width: parent.width
                height: logCol.implicitHeight + root.u * 4
                Column {
                  id: logCol
                  x: root.u * 4; y: root.u * 2
                  width: parent.width - root.u * 8
                  Row {
                    width: parent.width
                    spacing: root.u * 3
                    Caption { width: Style.font.body * 5; wrapMode: Text.NoWrap; text: root.ago(logRow.modelData.t) }
                    Body {
                      width: parent.width - Style.font.body * 5 - root.u * 3
                      text: logRow.modelData.why + (logRow.modelData.n > 1 ? "  ×" + logRow.modelData.n : "")
                        + (logRow.modelData.quests.length ? "  [quest: " + logRow.modelData.quests.join(", ") + "]" : "")
                    }
                  }
                  Caption { x: Style.font.body * 5 + root.u * 3; width: parent.width - x; text: logRow.modelData.gains }
                }
              }
            }
          }
        }
      }

      // The pixel dissolve: on a tab or view change the new content shows through
      // blocks that drop out in random order (about a fifth of a second).
      Canvas {
        id: dissolve
        anchors.fill: scroll
        z: 10
        visible: frame < frames
        property int frame: 0
        readonly property int frames: 10
        property var order: []
        readonly property int block: root.u * 4
        function play() {
          if (root.reduceMotion || !root.opened || width <= 0) return
          var cols = Math.ceil(width / block), rows = Math.ceil(height / block), o = []
          for (var i = 0; i < cols * rows; i++) o.push(i)
          for (var j = o.length - 1; j > 0; j--) { var k = Math.floor(Math.random() * (j + 1)); var t = o[j]; o[j] = o[k]; o[k] = t }
          order = o
          frame = 0
          requestPaint()
          dissolveTick.restart()
        }
        Timer { id: dissolveTick; interval: 18; repeat: true; onTriggered: { dissolve.frame++; if (dissolve.frame >= dissolve.frames) stop(); else dissolve.requestPaint() } }
        onPaint: {
          var c = getContext("2d")
          c.reset()
          if (frame >= frames) return
          var cols = Math.ceil(width / block)
          var keep = Math.floor(order.length * (1 - (frame + 1) / frames))
          c.fillStyle = Color.popups.background
          for (var i = 0; i < keep; i++) {
            var cell = order[i]
            c.fillRect((cell % cols) * block, Math.floor(cell / cols) * block, block, block)
          }
        }
      }
    }
  }
}
