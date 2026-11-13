import QtQuick
import QtQuick.Window
import Quickshell
import qs.Commons as Commons
import qs.Ui as Ui
import "Plugin" as Plugin

Window {
    id: window
    visible: true
    width: Commons.Style.space(820)
    height: Math.ceil(view.implicitHeight + card.contentTopInset + card.contentBottomInset)
    color: Commons.Color.background
    property bool returned: false
    readonly property string maliciousText: '<img src="https://example.invalid/tracker"><b>markup</b>'
    readonly property string outputDirectory: Quickshell.env("OMARCHY_STATS_TEST_OUTPUT")
    Ui.BorderSurface {
        id: card
        anchors.fill: parent
        color: Commons.Color.popups.background
        borderSpec: Commons.Border.surfaceSpec("popups", "border", Commons.Color.popups.border, Math.max(1, Commons.Style.space(2)))
        padding: Commons.Style.spacing.popupPadding
        radius: Commons.Style.cornerRadius

        Plugin.StatisticsView {
            id: view
            x: card.contentLeftInset
            y: card.contentTopInset
            width: card.width - card.contentLeftInset - card.contentRightInset
            today: new Date(2026, 10, 13, 12)
            cacheDirectory: decodeURIComponent(Qt.resolvedUrl("cache").toString().replace(/^file:\/\//, ""))
            returnControl: Component {
                Plugin.HeroButton { glyph: "󰅖"; onClicked: view.back() }
            }
            onBack: window.returned = true
        }
    }
    Ui.PanelToolTip { id: tooltip; text: window.maliciousText }
    Ui.PanelHero { id: heroProbe; visible: false; title: window.maliciousText; meta: window.maliciousText }

    function require(condition, message) {
        if (!condition) throw new Error(message)
    }
    function verifyPlainText(item) {
        if (item.textFormat !== undefined) require(item.textFormat === Text.PlainText, "Non-plain Text sink")
        if (item.children) for (var i = 0; i < item.children.length; i++) verifyPlainText(item.children[i])
    }
    function findItem(item, name) {
        if (item.objectName === name) return item
        if (item.children) {
            for (var i = 0; i < item.children.length; i++) {
                var found = findItem(item.children[i], name)
                if (found) return found
            }
        }
        return null
    }
    function setPalette(foreground, background, accent) {
        Commons.Color.foreground = foreground
        Commons.Color.background = background
        Commons.Color.popups.background = background
        Commons.Color.popups.border = accent
        Commons.Color.accent = accent
    }
    Timer {
        interval: 400; running: true
        onTriggered: {
            try {
                window.require(view.hasSnapshot && view.snapshot.totalTokens === Number(Quickshell.env("OMARCHY_STATS_TEST_TOTAL_TOKENS")), "Cached snapshot did not load before refresh")
                var metrics = window.findItem(view, "statisticsMetrics")
                window.require(metrics && metrics.visible && metrics.height > 25, "Summary metrics collapsed or disappeared")
                view.selectedAction = 2; view.activate()
                window.require(view.metric === 1, "Keyboard mode selection failed")
                view.selectedCell = view.lastDayCell
                var cell = view.selectedCell
                view.move(-1, 0)
                window.require(view.selectedCell === cell - 7, "Week navigation failed")
                view.selectedAction = 0; view.activate()
                window.require(window.returned, "Return action failed")
                window.require(tooltip.contentItem.textFormat === Text.PlainText && tooltip.contentItem.text === window.maliciousText, "Tooltip interpreted markup")
                window.verifyPlainText(heroProbe)
                window.verifyPlainText(view)
                var day = window.findItem(view, "statisticsDay")
                var originalX = day.x
                view.LayoutMirroring.enabled = true
                view.LayoutMirroring.childrenInherit = true
                window.require(Math.abs(day.x + originalX + day.width - view.width) < 0.01, "Calendar did not mirror in RTL")
                view.LayoutMirroring.enabled = false
                view.LayoutMirroring.childrenInherit = false
                view.metric = 0
                view.selectedCell = view.lastDayCell
                window.setPalette("#2665da", "#e2e3e8", "#2665da")
                lightShot.start()
            } catch (error) {
                console.error("UI_TEST_FAILED: " + error.message)
                Qt.exit(1)
            }
        }
    }
    Timer {
        id: lightShot
        interval: 120
        onTriggered: window.contentItem.grabToImage(function(result) {
            result.saveToFile(window.outputDirectory + "/statistics-light.png")
            window.setPalette("#cdd6f4", "#1e1e2e", "#89b4fa")
            darkShot.start()
        })
    }
    Timer {
        id: darkShot
        interval: 120
        onTriggered: window.contentItem.grabToImage(function(result) {
            result.saveToFile(window.outputDirectory + "/statistics-dark.png")
            window.require(view.ink.toString() === "#cdd6f4", "Live theme change did not reach text")
            window.require(view.accent.toString() === "#89b4fa", "Live theme change did not reach the calendar")
            console.info("UI_TEST_PASSED: cached display, keyboard navigation, return, plain text, light and dark live themes")
            Qt.quit()
        })
    }
}
