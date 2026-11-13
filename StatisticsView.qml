import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui as Ui
import "Calendar.js" as Calendar

Column {
    id: root
    property bool active: false
    property Component returnControl: null
    property string cacheDirectory: (Quickshell.env("XDG_CACHE_HOME") || Quickshell.env("HOME") + "/.cache") + "/omarchy/agent-statistics"
    property var snapshot: ({ days: {} })
    readonly property bool hasSnapshot: snapshot.totalTokens !== undefined
    property bool failed: false
    property int metric: 0
    property int selectedCell: lastDayCell
    property int selectedAction: 0
    property var today: new Date()
    readonly property var cells: Calendar.calendar(today)
    readonly property int weeks: cells.length / 7
    readonly property int lastDayCell: {
        for (var i = cells.length - 1; i >= 0; i--) if (cells[i].valid) return i
        return -1
    }
    readonly property real labelWidth: Style.space(30)
    readonly property real pitch: (width - labelWidth) / weeks
    readonly property real cellSize: Math.max(3, Math.min(Style.space(10), pitch - Style.space(3)))
    readonly property string field: ["tokens", "seconds", "prompts"][metric]
    readonly property color ink: Commons.Color.foreground
    readonly property color dim: Qt.darker(ink, 1.55)
    readonly property color accent: Commons.Color.accent
    readonly property real maximum: {
        var maximum = 1
        for (var i = 0; i < cells.length; i++) {
            var day = snapshot.days[cells[i].date]
            if (cells[i].valid && day) maximum = Math.max(maximum, day[field])
        }
        return maximum
    }
    signal back()
    spacing: Style.space(18)

    Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

    component PlainText: Text {
        textFormat: Text.PlainText
        color: root.ink
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
    }

    function refresh() {
        if (worker.running) return
        today = new Date()
        failed = false
        worker.running = true
    }
    onActiveChanged: if (active) refresh()

    function acceptSnapshot(raw, fresh) {
        if (raw.length > 2 * 1024 * 1024) throw new Error("Snapshot too large")
        snapshot = Calendar.validate(JSON.parse(raw))
        if (fresh) failed = false
    }

    FileView {
        id: cachedSummary
        path: root.cacheDirectory + "/summary.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try { root.acceptSnapshot(text(), false) } catch (e) { }
        }
    }

    function compact(value) {
        var n = Number(value || 0)
        if (n >= 1e9) return Commons.I18n.formatNumber(n / 1e9, 2) + "B"
        if (n >= 1e6) return Commons.I18n.formatNumber(n / 1e6, 1) + "M"
        if (n >= 1e3) return Commons.I18n.formatNumber(n / 1e3, 1) + "K"
        return Commons.I18n.formatNumber(n)
    }
    function duration(seconds) {
        var minutes = Math.floor(Number(seconds || 0) / 60)
        return strings.t("duration").arg(Commons.I18n.formatNumber(Math.floor(minutes / 60))).arg(Commons.I18n.formatNumber(minutes % 60))
    }
    function intensity(value) {
        if (!(value > 0)) return 0
        return Math.min(4, Math.max(1, Math.ceil(4 * Math.sqrt(value / maximum))))
    }
    function shade(level) {
        return Qt.alpha(accent, [0.12, 0.3, 0.5, 0.75, 1][level])
    }
    function calendarX(column, itemWidth) {
        var position = labelWidth + column * pitch
        return root.LayoutMirroring.enabled ? width - position - itemWidth : position
    }
    function activate() {
        if (selectedAction === 0) back()
        else metric = selectedAction - 1
    }
    function move(dx, dy) {
        if (dy > 0 && selectedCell < 0) selectedCell = lastDayCell
        else if (dy < 0 && selectedCell >= 0 && selectedCell % 7 === 0) selectedCell = -1
        else if (selectedCell >= 0) selectedCell = Math.max(0, Math.min(cells.length - 1, selectedCell + dx * 7 + dy))
        else selectedAction = (selectedAction + dx + 4) % 4
    }

    Timer { interval: 60000; repeat: true; running: root.active; onTriggered: root.refresh() }
    Process {
        id: worker
        command: ["nice", "-n", "10", "python3", "-B", decodeURIComponent(Qt.resolvedUrl("collect_statistics.py").toString().replace(/^file:\/\//, "")), "--cache", root.cacheDirectory + "/rollouts.json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.acceptSnapshot(text, true)
                } catch (e) { root.failed = true }
            }
        }
        stderr: StdioCollector { }
        onExited: function(code) {
            if (code !== 0) root.failed = true
            cachedSummary.reload()
        }
    }

    Ui.PanelHero {
        width: parent.width
        title: strings.t("heading")
        meta: worker.running ? (root.hasSnapshot ? strings.t("updating") : strings.t("loading")) : strings.t("title")
        iconComponent: Component {
            Image {
                readonly property color surface: Commons.Color.popups.background
                function luminance(channel) {
                    return channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4)
                }
                readonly property bool light: luminance(surface.r) * 0.2126 + luminance(surface.g) * 0.7152 + luminance(surface.b) * 0.0722 >= 0.5
                width: Style.font.display
                height: width
                source: Qt.resolvedUrl(light ? "assets/codex-light.svg" : "assets/codex.svg")
                sourceSize.width: width * 2
                sourceSize.height: height * 2
                fillMode: Image.PreserveAspectFit
            }
        }
        trailingControl: root.returnControl
    }

    Ui.PanelSeparator { foreground: root.ink }
    PlainText {
        text: root.hasSnapshot ? strings.tn("accounts", root.snapshot.accounts).arg(Commons.I18n.formatNumber(root.snapshot.accounts)) : strings.t("loadingHistory")
        color: root.dim
    }

    Row {
        objectName: "statisticsMetrics"
        width: parent.width
        Repeater {
            model: [
                { value: root.compact(root.snapshot.totalTokens), label: strings.t("totalTokens"), hint: strings.t("tokenHint") },
                { value: root.duration(root.snapshot.agentSeconds), label: strings.t("agentTime"), hint: strings.t("timeHint") },
                { value: root.compact(root.snapshot.totalSessions), label: strings.t("sessions"), hint: strings.t("sessionHint") },
                { value: strings.tn("days", root.snapshot.currentStreak || 0).arg(Commons.I18n.formatNumber(root.snapshot.currentStreak || 0)), label: strings.t("currentStreak"), hint: strings.t("streakHint") },
                { value: strings.tn("days", root.snapshot.longestStreak || 0).arg(Commons.I18n.formatNumber(root.snapshot.longestStreak || 0)), label: strings.t("longestStreak"), hint: strings.t("streakHint") }
            ]
            Item {
                required property var modelData
                width: root.width / 5
                height: metricContents.implicitHeight
                Column {
                    id: metricContents
                    width: parent.width
                    spacing: Style.space(6)
                    PlainText { width: parent.width; text: root.hasSnapshot ? modelData.value : "…"; font.bold: true; horizontalAlignment: Text.AlignHCenter }
                    PlainText { width: parent.width; text: modelData.label; color: root.dim; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter }
                }
                MouseArea { id: metricHover; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
                Ui.PanelToolTip { visible: metricHover.containsMouse; text: modelData.hint }
            }
        }
    }

    Row {
        spacing: Style.space(8)
        Repeater {
            model: [strings.t("tokens"), strings.t("agentTime"), strings.t("prompts")]
            Ui.Button {
                required property string modelData
                required property int index
                text: modelData
                selected: root.metric === index
                hasCursor: root.selectedCell < 0 && root.selectedAction === index + 1
                onClicked: root.metric = index
                onHovered: function(hovered) { if (hovered) { root.selectedAction = index + 1; root.selectedCell = -1 } }
            }
        }
    }

    Column {
        width: parent.width
        spacing: Style.space(10)
        PlainText { text: !root.hasSnapshot && worker.running ? strings.t("loadingHistory") : strings.t("lastYear"); color: root.dim }
        Item {
            width: parent.width
            height: Style.space(18)
            Repeater {
                model: root.cells
                PlainText {
                    required property var modelData
                    required property int index
                    visible: modelData.valid && modelData.day === 1
                    x: root.calendarX(Math.floor(index / 7), implicitWidth)
                    text: new Date(modelData.date + "T12:00:00").toLocaleDateString(Qt.locale(Commons.I18n.formatLocale), "MMM")
                    color: root.dim
                    font.pixelSize: Style.font.caption
                }
            }
        }
        Item {
            width: parent.width
            height: 7 * root.pitch
            Repeater {
                model: 7
                PlainText {
                    required property int index
                    x: root.LayoutMirroring.enabled ? root.width - root.labelWidth : 0
                    y: index * root.pitch
                    width: root.labelWidth
                    horizontalAlignment: root.LayoutMirroring.enabled ? Text.AlignRight : Text.AlignLeft
                    height: root.cellSize
                    text: new Date(2026, 10, 1 + index).toLocaleDateString(Qt.locale(Commons.I18n.formatLocale), "ddd").slice(0, 2)
                    font.pixelSize: Style.font.caption
                    color: root.dim
                }
            }
            Repeater {
                model: root.cells
                Rectangle {
                    required property var modelData
                    required property int index
                    readonly property var day: root.snapshot.days[modelData.date] || { tokens: 0, seconds: 0, prompts: 0 }
                    objectName: "statisticsDay"
                    x: root.calendarX(Math.floor(index / 7), width)
                    y: (index % 7) * root.pitch
                    width: root.cellSize
                    height: width
                    visible: modelData.valid
                    color: root.shade(root.intensity(day[root.field]))
                    border.width: root.selectedCell === index ? 1 : 0
                    border.color: root.ink
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        onEntered: root.selectedCell = index
                        onClicked: root.selectedCell = index
                    }
                }
            }
        }
        Row {
            spacing: Style.space(5)
            PlainText { text: strings.t("less"); color: root.dim }
            Repeater {
                model: 5
                Rectangle {
                    required property int index
                    width: root.cellSize; height: width
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.shade(index)
                }
            }
            PlainText { text: strings.t("more"); color: root.dim }
        }
        PlainText {
            width: parent.width
            readonly property var cell: root.selectedCell >= 0 ? root.cells[root.selectedCell] : null
            readonly property var day: cell && root.snapshot.days[cell.date] ? root.snapshot.days[cell.date] : { tokens: 0, seconds: 0, prompts: 0 }
            text: cell && cell.valid ? strings.t("dayDetail").arg(cell.date).arg(Commons.I18n.formatNumber(day.tokens)).arg(root.duration(day.seconds)).arg(Commons.I18n.formatNumber(day.prompts)) : strings.t("selectDay")
            color: root.dim
            wrapMode: Text.WordWrap
            height: Math.max(implicitHeight, Style.space(28))
        }
    }

    PlainText {
        visible: root.failed || root.snapshot.partialFiles > 0
        width: parent.width
        text: root.failed ? strings.t("error") : strings.t("partial")
        color: Commons.Color.urgent
        wrapMode: Text.WordWrap
        font.pixelSize: Style.font.caption
    }
}
