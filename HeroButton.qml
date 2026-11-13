import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui as Ui

// The native Agents hero control, shared with the preview renderer.
Rectangle {
  id: root
  signal clicked()
  signal hovered()
  property string glyph: ""
  property string tooltip: ""
  property bool hasCursor: false
  property string fontFamily: Style.font.family
  implicitWidth: Style.space(34)
  implicitHeight: implicitWidth
  radius: Style.cornerRadius
  color: Qt.rgba(Commons.Color.accent.r, Commons.Color.accent.g, Commons.Color.accent.b, hasCursor ? 0.3 : 0.12)
  border.width: hasCursor ? Math.max(1, Style.hoverBorderWidth) : 0
  border.color: Commons.Color.accent

  Text {
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: root.glyph
    color: Commons.Color.accent
    font.family: root.fontFamily
    font.pixelSize: Style.font.heading
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onEntered: root.hovered()
    onClicked: root.clicked()
  }

  Ui.PanelToolTip {
    visible: mouse.containsMouse
    text: root.tooltip
  }
}
