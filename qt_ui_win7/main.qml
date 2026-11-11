import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Window {
    id: window
    width: 1120
    height: 740
    minimumWidth: 980
    minimumHeight: 660
    visible: true
    title: "Achan"
    color: "#080D0A"
    flags: Qt.Window | Qt.FramelessWindowHint

    property bool allowClose: false
    property string currentPage: "dashboard"
    property string pendingPage: "dashboard"
    property string dialogMode: ""
    property color green: "#39E783"
    property color bg: "#0B0F0D"
    property color panel: "#121A15"
    property color panel2: "#151E19"
    property color border: "#29372F"
    property color textPrimary: "#E8F0EA"
    property color textMuted: "#A3B2A8"

    function tr(fa, en) { return bridge.language === "fa" ? fa : en }

    function navigateTo(page) {
        if (page === currentPage || pageTransition.running)
            return
        pendingPage = page
        pageTransition.restart()
    }
    function pageIndex() {
        if (currentPage === "settings") return 1
        if (currentPage === "updates") return 2
        if (currentPage === "about") return 3
        if (currentPage === "diagnostics") return 4
        return 0
    }
    function stageText(value) {
        if (value === "ready") return tr("آماده", "Ready")
        if (value === "checking") return tr("در حال بررسی", "Checking")
        if (value === "error") return tr("خطا", "Error")
        return tr("در انتظار", "Idle")
    }
    function stateText() {
        if (bridge.isConnected) return tr("متصل", "Connected")
        if (bridge.isBusy) return bridge.state === "starting" ? tr("در حال اتصال", "Connecting") : tr("در حال قطع", "Disconnecting")
        return tr("قطع", "Disconnected")
    }
    function connectionAccent() {
        if (bridge.isBusy) return "#E7B95E"
        if (bridge.isConnected) return "#39E783"
        return "#F16A72"
    }
    function connectionAccentSoft() {
        if (bridge.isBusy) return "#352B17"
        if (bridge.isConnected) return "#102719"
        return "#111A13"
    }
    function progressValue() {
        if (bridge.isConnected) return 1.0
        var states = [bridge.engineState, bridge.proxyState, bridge.dohState, bridge.tunnelState]
        var units = 0.0
        for (var i = 0; i < states.length; ++i) {
            if (states[i] === "ready") units += 1.0
            else if (states[i] === "checking") { units += 0.5; break }
            else break
        }
        if (bridge.isBusy && units === 0) return 0.035
        return units / 4.0
    }
    function updateDetailText() {
        if (bridge.updateStatus === "error") return bridge.updateMessage
        if (bridge.updateStatus === "available") return tr("نسخه جدید در کانال رسمی ویندوز پیدا شده است.", "A newer release was found in the official Windows channel.")
        if (bridge.updateStatus === "downloaded") return tr("فایل نصب پیش از نمایش، با Manifest رسمی تطبیق داده شده است.", "The installer was checked against the official release manifest.")
        if (bridge.updateStatus === "installer_opened") return tr("پس از بستن آچان، مراحل نصب را کامل کن.", "Complete setup after closing Achan.")
        return ""
    }
    function updateStatusText() {
        switch (bridge.updateStatus) {
        case "checking": return tr("در حال بررسی نسخه‌های رسمی…", "Checking official releases…")
        case "current": return tr("آخرین نسخه سازگار نصب است.", "You are using the latest compatible version.")
        case "available": return tr("نسخه جدید پیدا شد.", "A newer version is available.")
        case "downloading": return tr("در حال دریافت و بررسی فایل…", "Downloading and verifying installer…")
        case "downloaded": return tr("دانلود کامل و SHA-256 تأیید شد.", "Download complete; SHA-256 verified.")
        case "installing": return tr("در حال اجرای نصب‌کننده…", "Launching installer…")
        case "installer_opened": return tr("نصب‌کننده باز شد؛ مراحل نصب را کامل کن.", "Installer opened; complete setup to update.")
        case "demo": return tr("بررسی آپدیت در حالت نمایشی غیرفعال است.", "Update checks are disabled in demo mode.")
        case "error": return tr("بررسی یا دریافت آپدیت ناموفق بود.", "Update check or download failed.")
        default: return tr("برای بررسی نسخه جدید اقدام کن.", "Check whether a newer version is available.")
        }
    }
    onClosing: function(close) {
        if (!allowClose) {
            close.accepted = false
            requestClose()
        }
    }

    function requestClose() {
        if (bridge.isBusy) dialogMode = "busy"
        else if (bridge.isConnected) dialogMode = "exit"
        else bridge.closeAfterConfirmation()
    }
    function confirmClose() {
        dialogMode = ""
        bridge.closeAfterConfirmation()
    }

    Rectangle {
        id: shell
        anchors.fill: parent
        color: window.bg
        border.color: "#2A6040"
        border.width: 1
        Behavior on border.color { ColorAnimation { duration: 500 } }
        radius: 15
        clip: true

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // Custom titlebar: vector-drawn controls avoid missing-glyph squares.
            Rectangle {
                id: titleBar
                Layout.fillWidth: true
                Layout.preferredHeight: 58
                color: "#0C140F"

                MouseArea {
                    anchors.fill: parent
                    anchors.leftMargin: 225
                    anchors.rightMargin: 245
                    z: 0
                    onPressed: function(mouse) {
                        if (mouse.button === Qt.LeftButton) bridge.startSystemMove()
                    }
                    onDoubleClicked: window.visibility === Window.Maximized ? window.showNormal() : window.showMaximized()
                }

                RowLayout {
                    anchors.left: parent.left
                    anchors.leftMargin: 19
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 10
                    z: 2
                    Rectangle {
                        width: 34; height: 34; radius: 10
                        color: "#143522"; border.color: "#276A43"
                        Text {
                            anchors.centerIn: parent
                            text: "A"
                            color: window.green
                            font.family: "Segoe UI"
                            font.pixelSize: 23
                            font.bold: true
                        }
                    }
                    Column {
                        spacing: 0
                        Text {
                            text: "Achan"
                            color: window.textPrimary
                            font.family: "Segoe UI"
                            font.pixelSize: 18
                            font.bold: true
                        }
                        Text {
                            text: "NETWORK UTILITY"
                            color: "#7C9183"
                            font.family: "Segoe UI"
                            font.pixelSize: 8
                            font.letterSpacing: 1.15
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    text: bridge.demoMode ? "DEMO PREVIEW" : "NEXT GENERATION NETWORK UTILITY"
                    color: bridge.demoMode ? "#D9B96E" : "#799083"
                    font.family: "Segoe UI"
                    font.pixelSize: 9
                    font.letterSpacing: 1.45
                }

                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    z: 3

                    Rectangle {
                        width: 54; height: 34; radius: 8
                        color: langMouse.containsMouse ? "#183824" : "#111D15"
                        border.color: "#2C6742"
                        Text {
                            anchors.centerIn: parent
                            text: bridge.language === "fa" ? "EN" : "فا"
                            color: window.green
                            font.family: "Segoe UI"
                            font.pixelSize: 11
                            font.bold: true
                        }
                        MouseArea {
                            id: langMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: bridge.toggleLanguage()
                        }
                    }
                    WindowControl { kind: "minimize"; onClicked: window.showMinimized() }
                    WindowControl { kind: window.visibility === Window.Maximized ? "restore" : "maximize"; onClicked: window.visibility === Window.Maximized ? window.showNormal() : window.showMaximized() }
                    WindowControl { kind: "close"; isClose: true; onClicked: window.requestClose() }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#0B100D"
                // Mirror the application workspace for Persian without moving
                // the title bar or its existing window controls.
                LayoutMirroring.enabled: bridge.language === "fa"
                LayoutMirroring.childrenInherit: true

                // Lightweight decorative particles: visual ambience only, no network telemetry.
                Canvas {
                    id: particleField
                    anchors.fill: parent
                    z: 0
                    opacity: 0.12
                    property var particles: []

                    function initializeParticles() {
                        var points = []
                        for (var i = 0; i < 17; ++i) {
                            points.push({
                                x: (31 + i * 83) % Math.max(1, width),
                                y: (47 + i * 59) % Math.max(1, height),
                                vx: (i % 3 === 0 ? 0.20 : (i % 2 === 0 ? -0.13 : 0.11)),
                                vy: (i % 2 === 0 ? 0.10 : -0.12),
                                r: 1 + (i % 3) * 0.35
                            })
                        }
                        particles = points
                        requestPaint()
                    }

                    function advance() {
                        if (width < 2 || height < 2 || particles.length === 0)
                            return
                        var moved = []
                        for (var i = 0; i < particles.length; ++i) {
                            var p = particles[i]
                            var nx = p.x + p.vx
                            var ny = p.y + p.vy
                            if (nx < 2 || nx > width - 2) p.vx = -p.vx
                            if (ny < 2 || ny > height - 2) p.vy = -p.vy
                            nx = Math.max(2, Math.min(width - 2, nx))
                            ny = Math.max(2, Math.min(height - 2, ny))
                            moved.push({x: nx, y: ny, vx: p.vx, vy: p.vy, r: p.r})
                        }
                        particles = moved
                        requestPaint()
                    }

                    onPaint: {
                        var c = getContext("2d")
                        c.clearRect(0, 0, width, height)
                        for (var i = 0; i < particles.length; ++i) {
                            var a = particles[i]
                            for (var j = i + 1; j < particles.length; ++j) {
                                var b = particles[j]
                                var dx = a.x - b.x
                                var dy = a.y - b.y
                                var d = Math.sqrt(dx * dx + dy * dy)
                                if (d < 118) {
                                    c.beginPath()
                                    c.moveTo(a.x, a.y)
                                    c.lineTo(b.x, b.y)
                                    c.strokeStyle = "#39E783"
                                    c.globalAlpha = (1 - d / 118) * 0.12
                                    c.lineWidth = 1
                                    c.stroke()
                                }
                            }
                            c.beginPath()
                            c.arc(a.x, a.y, a.r, 0, Math.PI * 2)
                            c.fillStyle = "#65F4A0"
                            c.globalAlpha = 0.35
                            c.fill()
                        }
                        c.globalAlpha = 1
                    }
                    onWidthChanged: if (particles.length === 0) initializeParticles()
                }

                Timer {
                    interval: 45
                    repeat: true
                    running: window.currentPage === "dashboard" && window.visible
                    onTriggered: particleField.advance()
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10
                    z: 1

                    // Left navigation rail.
                    Rectangle {
                        visible: false
                        Layout.preferredWidth: 194
                        Layout.fillHeight: true
                        radius: 15
                        color: "#C10D1510"
                        border.color: window.border
                        Behavior on border.color { ColorAnimation { duration: 260 } }

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 7
                            Text {
                                text: tr("منوی اصلی", "WORKSPACE")
                                color: "#72877A"
                                font.family: "Segoe UI"
                                font.pixelSize: 9
                                font.bold: true
                                Layout.leftMargin: 7
                                Layout.topMargin: 6
                                Layout.bottomMargin: 7
                            }
                            NavItem { Layout.fillWidth: true; label: window.tr("داشبورد", "Dashboard"); glyph: "⌂"; selected: window.currentPage === "dashboard"; onClicked: window.navigateTo("dashboard") }
                            NavItem { Layout.fillWidth: true; label: window.tr("تنظیمات", "Settings"); glyph: "⚙"; selected: window.currentPage === "settings"; onClicked: window.navigateTo("settings") }
                            NavItem { Layout.fillWidth: true; label: window.tr("به‌روزرسانی", "Updates"); glyph: "↻"; selected: window.currentPage === "updates"; onClicked: window.navigateTo("updates") }
                            NavItem { Layout.fillWidth: true; label: window.tr("درباره آچان", "About Achan"); glyph: "ⓘ"; selected: window.currentPage === "about"; onClicked: window.navigateTo("about") }
                            NavItem { Layout.fillWidth: true; label: window.tr("گزارش و عیب‌یابی", "Logs & diagnostics"); glyph: "≡"; selected: window.currentPage === "diagnostics"; onClicked: { window.navigateTo("diagnostics"); bridge.refreshDiagnostics() } }
                            Item { Layout.fillHeight: true }
                            Rectangle { Layout.fillWidth: true; height: 1; color: "#26382D" }
                            Rectangle {
                                Layout.fillWidth: true
                                radius: 11
                                color: "#101C14"
                                border.color: "#223D2B"
                                implicitHeight: 78
                                Column {
                                    anchors.centerIn: parent
                                    spacing: 4
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "✦"
                                        color: window.green
                                        font.pixelSize: 18
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "Made by Faraj"
                                        color: "#B3C3B7"
                                        font.family: "Segoe UI"
                                        font.pixelSize: 10
                                    }
                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "v" + bridge.version
                                        color: "#708478"
                                        font.family: "Segoe UI"
                                        font.pixelSize: 8
                                    }
                                }
                            }
                        }
                    }

                    // Main page stack.
                    StackLayout {
                        id: pages
                        Layout.fillWidth: true
                        Layout.maximumWidth: 960
                        Layout.fillHeight: true
                        Layout.alignment: Qt.AlignHCenter
                        currentIndex: window.pageIndex()
                        opacity: 1.0
                        transformOrigin: Item.Center

                        // DASHBOARD — focused connection control and animated connection progress.
                        Item {
                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 12
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 54
                                    Column {
                                        spacing: 1
                                        Text { text: window.tr("نمای کلی", "OVERVIEW"); color: "#83A28E"; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 1 }
                                        Text { text: window.tr("داشبورد", "Dashboard"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 21; font.bold: true }
                                        Text { text: window.tr("مدیریت و کنترل اتصال آچان", "Manage and control your Achan connection"); color: window.textMuted; font.family: "Segoe UI"; font.pixelSize: 10 }
                                    }
                                    Item { Layout.fillWidth: true }
                                    StatusPill { }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Layout.minimumHeight: 390
                                    spacing: 12

                                    Rectangle {
                                        id: connectionPanel
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: 17
                                        gradient: Gradient {
                                            GradientStop { position: 0.0; color: "#D0142018" }
                                            GradientStop { position: 0.54; color: "#C70F1913" }
                                            GradientStop { position: 1.0; color: "#D10B140F" }
                                        }
                                        border.width: 1
                                        border.color: window.border
                                        Behavior on border.color { ColorAnimation { duration: 360 } }
                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 16
                                            spacing: 5
                                            RowLayout {
                                                Layout.fillWidth: true
                                                Layout.preferredHeight: 20
                                                Text { text: window.tr("اتصال آچان", "Achan connection"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 12; font.bold: true }
                                                Item { Layout.fillWidth: true }
                                                Text { text: bridge.demoMode ? "DEMO" : "TUNNEL CONTROL"; color: "#718879"; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 1 }
                                            }
                                            Item { Layout.fillHeight: true }
                                            Item {
                                                Layout.alignment: Qt.AlignHCenter
                                                Layout.preferredWidth: 176
                                                Layout.preferredHeight: 168
                                                Canvas {
                                                    id: powerGlow
                                                    width: 190; height: 190
                                                    anchors.centerIn: parent
                                                    // Show the halo only after the backend confirms a live connection.
                                                    visible: bridge.isConnected
                                                    opacity: bridge.isConnected ? 0.78 : 0.0
                                                    onPaint: {
                                                        var c = getContext("2d")
                                                        c.clearRect(0, 0, width, height)
                                                        var g = c.createRadialGradient(width/2, height/2, 8, width/2, height/2, 92)
                                                        if (bridge.isConnected) {
                                                            g.addColorStop(0, "rgba(57,231,131,0.25)")
                                                            g.addColorStop(0.55, "rgba(57,231,131,0.10)")
                                                        } else if (bridge.isBusy) {
                                                            g.addColorStop(0, "rgba(231,185,94,0.24)")
                                                            g.addColorStop(0.55, "rgba(231,185,94,0.08)")
                                                        } else {
                                                            g.addColorStop(0, "rgba(241,106,114,0.20)")
                                                            g.addColorStop(0.55, "rgba(241,106,114,0.07)")
                                                        }
                                                        g.addColorStop(1, "rgba(0,0,0,0)")
                                                        c.fillStyle = g
                                                        c.fillRect(0, 0, width, height)
                                                    }
                                                    Behavior on opacity { NumberAnimation { duration: 420 } }
                                                    SequentialAnimation on scale {
                                                        running: bridge.isConnected
                                                        loops: Animation.Infinite
                                                        NumberAnimation { to: 1.045; duration: 1250; easing.type: Easing.InOutSine }
                                                        NumberAnimation { to: 1.0; duration: 1250; easing.type: Easing.InOutSine }
                                                    }
                                                }
                                                Rectangle {
                                                    id: powerHalo
                                                    width: 164; height: 164; radius: 82
                                                    anchors.centerIn: parent
                                                    color: window.connectionAccentSoft()
                                                    visible: bridge.isConnected
                                                    opacity: bridge.isConnected ? 0.92 : 0.0
                                                    Behavior on opacity { NumberAnimation { duration: 300 } }
                                                    Behavior on color { ColorAnimation { duration: 220 } }
                                                    SequentialAnimation on scale {
                                                        running: bridge.isConnected
                                                        loops: Animation.Infinite
                                                        NumberAnimation { to: 1.035; duration: 1100; easing.type: Easing.InOutSine }
                                                        NumberAnimation { to: 1.0; duration: 1100; easing.type: Easing.InOutSine }
                                                    }
                                                }
                                                Canvas {
                                                    id: powerRings
                                                    width: 154; height: 154
                                                    anchors.centerIn: parent
                                                    visible: bridge.isConnected
                                                    onPaint: {
                                                        var c = getContext("2d")
                                                        c.clearRect(0, 0, width, height)
                                                        c.lineWidth = 3
                                                        c.strokeStyle = window.connectionAccent()
                                                        c.globalAlpha = 0.92
                                                        c.beginPath(); c.arc(width/2, height/2, 73, -Math.PI*0.82, Math.PI*0.72); c.stroke()
                                                        c.lineWidth = 2
                                                        c.globalAlpha = 0.45
                                                        c.strokeStyle = bridge.isConnected ? "#55EFA0" : bridge.isBusy ? "#A88B46" : "#8D3D48"
                                                        c.beginPath(); c.arc(width/2, height/2, 64, Math.PI*0.18, Math.PI*1.78); c.stroke()
                                                        c.globalAlpha = 1
                                                    }
                                                    NumberAnimation on rotation {
                                                        running: bridge.isConnected
                                                        from: 0; to: 360; duration: 5200; loops: Animation.Infinite
                                                    }
                                                    Behavior on rotation { NumberAnimation { duration: 180 } }
                                                }
                                                Rectangle {
                                                    id: powerButton
                                                    width: 120; height: 120; radius: 60
                                                    anchors.centerIn: parent
                                                    gradient: Gradient {
                                                        GradientStop { position: 0.0; color: bridge.isConnected ? "#17291E" : bridge.isBusy ? "#2B2416" : "#18221B" }
                                                        GradientStop { position: 1.0; color: bridge.isConnected ? "#0C1510" : bridge.isBusy ? "#17130D" : "#0D1510" }
                                                    }
                                                    border.width: powerMouse.containsMouse ? 2.5 : 2
                                                    border.color: powerMouse.containsMouse ? (bridge.isConnected ? "#83FFB4" : bridge.isBusy ? "#F5D17C" : "#A3B2A8") : bridge.isConnected ? "#39E783" : bridge.isBusy ? "#E7B95E" : "#435247"
                                                    scale: powerMouse.pressed ? 0.955 : powerMouse.containsMouse ? 1.045 : 1.0
                                                    Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
                                                    Behavior on border.color { ColorAnimation { duration: 220 } }
                                                    Rectangle {
                                                        anchors.fill: parent
                                                        anchors.margins: 7
                                                        radius: width/2
                                                        color: "transparent"
                                                        border.color: bridge.isConnected ? "#286B43" : bridge.isBusy ? "#69572E" : "#36483B"
                                                        border.width: 1
                                                        Behavior on border.color { ColorAnimation { duration: 180 } }
                                                    }
                                                    Canvas {
                                                        id: powerGlyph
                                                        anchors.centerIn: parent
                                                        width: 58; height: 58
                                                        onPaint: {
                                                            var c = getContext("2d")
                                                            c.clearRect(0, 0, width, height)
                                                            c.strokeStyle = bridge.isConnected ? "#39E783" : bridge.isBusy ? "#E7B95E" : "#84958A"
                                                            c.lineWidth = 5.2
                                                            c.lineCap = "round"
                                                            c.lineJoin = "round"
                                                            c.beginPath()
                                                            c.moveTo(width/2, 4)
                                                            c.lineTo(width/2, 27)
                                                            c.stroke()
                                                            c.beginPath()
                                                            c.arc(width/2, height/2 + 5, 21, -Math.PI*0.22, Math.PI*1.22, false)
                                                            c.stroke()
                                                        }
                                                    }
                                                    MouseArea {
                                                        id: powerMouse
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: bridge.isBusy ? Qt.ArrowCursor : Qt.PointingHandCursor
                                                        enabled: !bridge.isBusy
                                                        onClicked: bridge.toggleConnection()
                                                    }
                                                }
                                            }
                                            RowLayout {
                                                Layout.alignment: Qt.AlignHCenter
                                                spacing: 7
                                                Canvas {
                                                    id: stateSpinner
                                                    width: 16; height: 16
                                                    visible: bridge.isBusy
                                                    onPaint: {
                                                        var c = getContext("2d")
                                                        c.clearRect(0, 0, width, height)
                                                        c.beginPath()
                                                        c.arc(width/2, height/2, 6, -Math.PI*0.78, Math.PI*0.82)
                                                        c.strokeStyle = "#E7B95E"
                                                        c.lineWidth = 2
                                                        c.lineCap = "round"
                                                        c.stroke()
                                                    }
                                                    NumberAnimation on rotation {
                                                        running: bridge.isBusy
                                                        from: 0; to: 360; duration: 850; loops: Animation.Infinite
                                                    }
                                                }
                                                Text {
                                                    text: window.stateText()
                                                    color: window.connectionAccent()
                                                    font.family: "Segoe UI"
                                                    font.pixelSize: 14
                                                    font.bold: true
                                                    Behavior on color { ColorAnimation { duration: 260 } }
                                                }
                                            }
                                            Text {
                                                Layout.alignment: Qt.AlignHCenter
                                                text: bridge.isBusy ? window.tr("لطفاً تا پایان عملیات صبر کن", "Please wait for the operation to finish") : bridge.isConnected ? window.tr("اتصال سراسری فعال است", "System tunnel is active") : window.tr("برای شروع، دکمه را لمس کن", "Press the button to connect")
                                                color: bridge.isConnected ? "#83B998" : bridge.isBusy ? "#D8BD7D" : "#D38B91"
                                                font.family: "Segoe UI"
                                                font.pixelSize: 9
                                                Behavior on color { ColorAnimation { duration: 300 } }
                                            }
                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                Layout.topMargin: 2
                                                spacing: 5
                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    Text { text: window.tr("روند اتصال", "Connection progress"); color: "#A9BBAE"; font.family: "Segoe UI"; font.pixelSize: 9; font.bold: true }
                                                    Item { Layout.fillWidth: true }
                                                    Text { text: Math.round(window.progressValue() * 100) + "%"; color: window.connectionAccent(); font.family: "Segoe UI"; font.pixelSize: 9; font.bold: true }
                                                }
                                                Rectangle {
                                                    id: progressTrack
                                                    Layout.fillWidth: true
                                                    height: 5
                                                    radius: 3
                                                    color: "#1B2A20"
                                                    Rectangle {
                                                        height: parent.height
                                                        width: parent.width * window.progressValue()
                                                        radius: 3
                                                        color: window.connectionAccent()
                                                        Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
                                                        Behavior on color { ColorAnimation { duration: 180 } }
                                                    }
                                                }
                                                RowLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 5
                                                    ProgressStep { Layout.fillWidth: true; label: window.tr("موتور", "Engine"); statusState: bridge.engineState }
                                                    ProgressStep { Layout.fillWidth: true; label: window.tr("پراکسی", "Proxy"); statusState: bridge.proxyState }
                                                    ProgressStep { Layout.fillWidth: true; label: window.tr("DNS امن", "Secure DNS"); statusState: bridge.dohState }
                                                    ProgressStep { Layout.fillWidth: true; label: window.tr("تونل", "Tunnel"); statusState: bridge.tunnelState }
                                                }
                                            }
                                             RowLayout {
                                                 Layout.fillWidth: true
                                                 spacing: 8
                                                 DashboardMetric { Layout.fillWidth: true; label: window.tr("پروکسی محلی", "Local proxy"); value: "127.0.0.1:4525"; glyph: "⌁"; active: bridge.proxyState === "ready" }
                                                 DashboardMetric { Layout.fillWidth: true; label: window.tr("حالت DNS", "DNS mode"); value: "DNS over HTTPS"; glyph: "◌"; active: bridge.dohState === "ready" }
                                                 DashboardMetric { Layout.fillWidth: true; label: window.tr("مسیریابی", "Routing"); value: "TCP / TUN"; glyph: "⇄"; active: bridge.tunnelState === "ready" }
                                             }
                                             Rectangle {
                                                 Layout.fillWidth: true
                                                 Layout.preferredHeight: 34
                                                 radius: 9
                                                 color: bridge.noticeLevel === "error" ? "#321A1C" : bridge.noticeLevel === "warning" ? "#2C2618" : "#11291B"
                                                 border.color: bridge.noticeLevel === "error" ? "#79383D" : bridge.noticeLevel === "warning" ? "#66532A" : "#28633D"
                                                 Text {
                                                     anchors.fill: parent
                                                     anchors.leftMargin: 12
                                                     anchors.rightMargin: 12
                                                     verticalAlignment: Text.AlignVCenter
                                                     horizontalAlignment: bridge.language === "fa" ? Text.AlignRight : Text.AlignLeft
                                                     text: bridge.demoMode ? window.tr("پیش‌نمایش نمایشی است؛ هیچ تغییری در شبکه ایجاد نمی‌شود.", "Demo preview only; no network settings are changed.") : (bridge.language === "fa" ? bridge.notice : bridge.noticeEnglish)
                                                     color: "#C8D7CC"
                                                     font.family: "Segoe UI"
                                                     font.pixelSize: 9
                                                     elide: Text.ElideRight
                                                 }
                                             }
                                            Item { Layout.fillHeight: true }
                                        }

                                    }
                                }


                            }
                        }

                        // SETTINGS PAGE
                        Item {
                            GridLayout {
                                anchors.fill: parent; columns: 2; columnSpacing: 12; rowSpacing: 12
                                PageHeading { Layout.columnSpan: 2; eyebrowText: window.tr("تنظیمات برنامه", "APP PREFERENCES"); titleText: window.tr("تنظیمات", "Settings"); subtitleText: window.tr("ترجیحات رابط و به‌روزرسانی", "Interface and update preferences") }
                                Rectangle {
                                    Layout.fillWidth: true; Layout.preferredHeight: 104
                                    radius: 15; color: "#111913"; border.color: window.border
                                    Behavior on border.color { ColorAnimation { duration: 260 } }
                                    RowLayout {
                                        anchors.fill: parent; anchors.margins: 16; spacing: 12
                                        ColumnLayout {
                                            Layout.fillWidth: true; spacing: 4
                                            Text { text: window.tr("زبان برنامه", "Application language"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 13; font.bold: true }
                                            Text { text: window.tr("زبان نمایش و جهت چیدمان را انتخاب کن.", "Choose the display language and layout direction."); color: window.textMuted; font.family: "Segoe UI"; font.pixelSize: 9; wrapMode: Text.WordWrap }
                                        }
                                        SmallButton { label: "فارسی"; selected: bridge.language === "fa"; onClicked: { if (bridge.language !== "fa") bridge.toggleLanguage() } }
                                        SmallButton { label: "English"; selected: bridge.language === "en"; onClicked: { if (bridge.language !== "en") bridge.toggleLanguage() } }
                                    }
                                }
                                Rectangle {
                                    Layout.fillWidth: true; Layout.preferredHeight: 116
                                    radius: 15; color: "#111913"; border.color: window.border
                                    Behavior on border.color { ColorAnimation { duration: 260 } }
                                    RowLayout {
                                        anchors.fill: parent; anchors.margins: 16; spacing: 12
                                        ColumnLayout {
                                            Layout.fillWidth: true; spacing: 4
                                            Text { text: window.tr("به‌روزرسانی خودکار", "Automatic updates"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 13; font.bold: true }
                                            Text { text: window.tr("انتشار رسمی GitHub روزی یک‌بار بررسی می‌شود.", "Official GitHub releases are checked once per day."); color: window.textMuted; font.family: "Segoe UI"; font.pixelSize: 9; wrapMode: Text.WordWrap }
                                        }
                                        Switch {
                                            checked: bridge.autoUpdateChecks
                                            onToggled: bridge.setAutoUpdateChecks(checked)
                                        }
                                    }
                                }
                                Rectangle {
                                    Layout.columnSpan: 2
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    radius: 15; color: "#111913"; border.color: window.border
                                    Behavior on border.color { ColorAnimation { duration: 260 } }
                                    ColumnLayout {
                                        anchors.fill: parent; anchors.margins: 16; spacing: 8
                                        Text { text: window.tr("اطلاعات اتصال", "Connection details"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 13; font.bold: true }
                                        DividerLine { }
                                        InfoRow { label: window.tr("پراکسی محلی", "Local proxy"); value: "127.0.0.1:4525" }
                                        InfoRow { label: window.tr("DNS", "DNS"); value: "DNS over HTTPS" }
                                        InfoRow { label: window.tr("مسیریابی", "Routing"); value: "TCP / TUN" }
                                    }
                                }
                            }
                        }

                        // UPDATES PAGE
                        Item {
                            ColumnLayout {
                                anchors.fill: parent; spacing: 14
                                PageHeading { eyebrowText: window.tr("انتشار رسمی", "STABLE CHANNEL"); titleText: window.tr("به‌روزرسانی آچان", "Achan updates"); subtitleText: window.tr("دریافت نسخه رسمی متناسب با ویندوز", "Official release channel for this Windows build") }
                                Rectangle {
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    radius: 17; color: "#D0101A14"; border.color: window.border
                                    Behavior on border.color { ColorAnimation { duration: 260 } }
                                    ColumnLayout {
                                        anchors.fill: parent; anchors.margins: 22; spacing: 14
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 12
                                            Rectangle {
                                                width: 50; height: 50; radius: 14; color: "#163D27"; border.color: "#31744B"
                                                Text { anchors.centerIn: parent; text: "A"; color: window.green; font.family: "Segoe UI"; font.pixelSize: 30; font.bold: true }
                                            }
                                            ColumnLayout {
                                                Layout.fillWidth: true; spacing: 3
                                                Text { text: window.tr("نسخه فعلی", "CURRENT VERSION"); color: "#8BA193"; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 0.5 }
                                                Text { text: "Achan " + bridge.version; color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 19; font.bold: true }
                                                Text { text: bridge.updateChannel; color: "#7A8F80"; font.family: "Segoe UI"; font.pixelSize: 9; LayoutMirroring.enabled: false }
                                            }
                                            Rectangle {
                                                radius: 14; height: 28; color: bridge.updateStatus === "error" ? "#321A1C" : "#112218"; border.color: bridge.updateStatus === "error" ? "#79383D" : "#28543A"
                                                implicitWidth: updateBadgeText.implicitWidth + 24
                                                Row { anchors.centerIn: parent; spacing: 7
                                                    Rectangle { width: 6; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter; color: bridge.updateStatus === "error" ? "#E56B76" : "#55D58A" }
                                                    Text { id: updateBadgeText; text: bridge.updateStatus === "error" ? window.tr("خطا", "Issue") : bridge.updateStatus === "available" ? window.tr("نسخه تازه", "Update available") : bridge.updateStatus === "checking" ? window.tr("در حال بررسی", "Checking") : window.tr("کانال پایدار", "Stable channel"); color: bridge.updateStatus === "error" ? "#E7838A" : "#55D58A"; font.family: "Segoe UI"; font.pixelSize: 9 }
                                                }
                                            }
                                        }
                                        DividerLine { }
                                        Text { text: window.updateStatusText(); color: bridge.updateStatus === "error" ? "#F28A8D" : bridge.updateStatus === "available" || bridge.updateStatus === "downloaded" ? window.green : window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 13; font.bold: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                        Text { text: window.updateDetailText(); color: bridge.updateStatus === "error" ? "#E99A9E" : "#899A8F"; font.family: "Segoe UI"; font.pixelSize: 9; wrapMode: Text.WordWrap; Layout.fillWidth: true; visible: text.length > 0 }
                                        Text { text: bridge.updateVersion.length > 0 ? "Version " + bridge.updateVersion : ""; color: window.green; font.family: "Segoe UI"; font.pixelSize: 11; visible: bridge.updateVersion.length > 0 }
                                        ScrollView {
                                            Layout.fillWidth: true; Layout.fillHeight: true
                                            visible: bridge.updateNotes.length > 0
                                            TextArea {
                                                readOnly: true; wrapMode: TextEdit.WordWrap; selectByMouse: true
                                                text: bridge.updateNotes
                                                color: "#B7C8BC"; font.family: "Segoe UI"; font.pixelSize: 9
                                                background: Rectangle { color: "#0B120D"; radius: 10; border.color: "#24392A" }
                                                LayoutMirroring.enabled: false
                                                horizontalAlignment: TextEdit.AlignLeft
                                            }
                                        }
                                        ProgressBar {
                                            Layout.fillWidth: true
                                            from: 0; to: 100; value: bridge.updatePercent
                                            visible: bridge.updateStatus === "downloading"
                                        }
                                        RowLayout {
                                            Layout.fillWidth: true
                                            ActionButton { label: window.tr("بررسی نسخه جدید", "Check for updates"); accent: false; enabled: bridge.updateStatus !== "checking" && bridge.updateStatus !== "downloading"; onClicked: bridge.checkForUpdates() }
                                            ActionButton { label: window.tr("دریافت نسخه", "Download update"); accent: true; visible: bridge.updateCanDownload; onClicked: bridge.downloadUpdate() }
                                            ActionButton { label: window.tr("اجرای نصب‌کننده", "Run installer"); accent: true; visible: bridge.updateDownloaded; enabled: bridge.updateCanInstall; onClicked: bridge.installUpdate() }
                                        }
                                        Text { text: window.tr("فایل نصب‌کننده پیش از استفاده با اندازه و SHA-256 ثبت‌شده در Manifest رسمی بررسی می‌شود.", "The installer is verified against the official manifest's file size and SHA-256 before it is offered."); color: "#738779"; font.family: "Segoe UI"; font.pixelSize: 8; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                    }
                                }
                            }
                        }

                        // ABOUT PAGE
                        Item {
                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 12
                                PageHeading { eyebrowText: window.tr("درباره برنامه", "ABOUT ACHAN"); titleText: window.tr("درباره آچان", "About Achan"); subtitleText: window.tr("اطلاعات نسخه و فناوری‌ها", "Version and technology information") }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    spacing: 12
                                    Rectangle {
                                        Layout.preferredWidth: 310
                                        Layout.fillHeight: true
                                        radius: 20
                                        color: "#101B14"
                                        border.color: "#294331"
                                        ColumnLayout {
                                            anchors.centerIn: parent
                                            spacing: 8
                                            Rectangle {
                                                Layout.alignment: Qt.AlignHCenter
                                                width: 78; height: 78; radius: 23
                                                color: "#143522"; border.color: "#2E7A4A"
                                                Text { anchors.centerIn: parent; text: "A"; color: window.green; font.family: "Segoe UI"; font.pixelSize: 48; font.bold: true }
                                            }
                                            Text { Layout.alignment: Qt.AlignHCenter; text: "NETWORK UTILITY"; color: "#83A28E"; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 1.1 }
                                            Text { Layout.alignment: Qt.AlignHCenter; text: "Achan"; color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 22; font.bold: true }
                                            Text { Layout.alignment: Qt.AlignHCenter; Layout.maximumWidth: 250; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; text: window.tr("ابزار مدیریت اتصال شبکه در ویندوز", "Windows network connection utility"); color: window.textMuted; font.family: "Segoe UI"; font.pixelSize: 10 }
                                            Rectangle {
                                                Layout.alignment: Qt.AlignHCenter
                                                Layout.topMargin: 7
                                                radius: 9; color: "#122319"; border.color: "#284932"
                                                implicitWidth: versionLabel.implicitWidth + 22; implicitHeight: 30
                                                Text { id: versionLabel; anchors.centerIn: parent; text: window.tr("نسخه ", "Version ") + bridge.version; color: "#9FC8AA"; font.family: "Segoe UI"; font.pixelSize: 10; LayoutMirroring.enabled: false; horizontalAlignment: Text.AlignLeft }
                                            }
                                        }
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: 20
                                        color: "#101713"
                                        border.color: window.border
                                        ColumnLayout {
                                            anchors.fill: parent; anchors.margins: 22; spacing: 11
                                            Text { text: window.tr("اطلاعات پروژه", "PROJECT INFO"); color: "#83A28E"; font.family: "Segoe UI"; font.pixelSize: 9; font.letterSpacing: 1 }
                                            Text { text: window.tr("ساخته‌شده با دقت", "Built with care"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 17; font.bold: true }
                                            Text { Layout.fillWidth: true; text: window.tr("آچان اتصال شبکه را از یک فضای کاری روشن و ساده مدیریت می‌کند.", "Achan manages network connectivity in a clear, focused workspace."); color: window.textMuted; font.family: "Segoe UI"; font.pixelSize: 10; wrapMode: Text.WordWrap }
                                            DividerLine { Layout.topMargin: 4 }
                                            InfoRow { label: window.tr("نسخه", "Version"); value: bridge.version }
                                            InfoRow { label: window.tr("کانال سیستم", "System channel"); value: bridge.updateChannel }
                                            InfoRow { label: window.tr("فناوری", "Technology"); value: "PySide6 · Qt Quick · QML" }
                                            InfoRow { label: window.tr("طراحی و توسعه", "Design & development"); value: "Made by Faraj" }
                                            Item { Layout.fillHeight: true }
                                            RowLayout {
                                                Layout.fillWidth: true
                                                Rectangle { width: 24; height: 24; radius: 7; color: "#143522"; border.color: "#276A43"; Text { anchors.centerIn: parent; text: "A"; color: window.green; font.pixelSize: 15; font.bold: true } }
                                                Text { text: window.tr("ساخته‌شده برای اتصال بهتر", "Made for a better connection"); color: "#84978A"; font.family: "Segoe UI"; font.pixelSize: 9 }
                                                Item { Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // LOGS & DIAGNOSTICS PAGE
                        Item {
                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 12
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 54
                                    Column {
                                        spacing: 1
                                        Text { text: window.tr("جزئیات فنی", "TECHNICAL DETAILS"); color: "#83A28E"; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 1 }
                                        Text { text: window.tr("گزارش و عیب‌یابی", "Logs & diagnostics"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 21; font.bold: true }
                                        Text { text: window.tr("وضعیت اجزای آچان را بررسی کن", "Review Achan component status"); color: window.textMuted; font.family: "Segoe UI"; font.pixelSize: 10 }
                                    }
                                    Item { Layout.fillWidth: true }
                                    ActionButton { label: window.tr("تازه‌سازی", "Refresh"); accent: false; onClicked: bridge.refreshDiagnostics() }
                                    ActionButton { label: window.tr("کپی گزارش", "Copy log"); accent: true; onClicked: bridge.copyDiagnostics() }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    spacing: 12
                                    Rectangle {
                                        Layout.preferredWidth: 286
                                        Layout.fillHeight: true
                                        radius: 17; color: "#101713"; border.color: window.border
                                        ColumnLayout {
                                            anchors.fill: parent; anchors.margins: 16; spacing: 8
                                            RowLayout {
                                                Layout.fillWidth: true
                                                ColumnLayout {
                                                    Layout.fillWidth: true; spacing: 3
                                                    Text { text: window.tr("وضعیت سیستم", "SYSTEM STATUS"); color: "#83A28E"; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 1 }
                                                    Text { text: window.tr("اجزای سرویس", "Service components"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 14; font.bold: true }
                                                }
                                                Rectangle { width: 7; height: 7; radius: 4; color: "#51CF83" }
                                            }
                                            DividerLine { }
                                            DiagnosticRow { labelText: "Core Engine"; valueText: window.stageText(bridge.engineState); stateValue: bridge.engineState }
                                            DiagnosticRow { labelText: "Local Proxy"; valueText: window.stageText(bridge.proxyState); stateValue: bridge.proxyState }
                                            DiagnosticRow { labelText: "DNS over HTTPS"; valueText: window.stageText(bridge.dohState); stateValue: bridge.dohState }
                                            DiagnosticRow { labelText: "TUN Adapter"; valueText: window.stageText(bridge.tunnelState); stateValue: bridge.tunnelState }
                                            Item { Layout.fillHeight: true }
                                            Text { Layout.fillWidth: true; text: "127.0.0.1:4525"; color: "#718779"; font.family: "Consolas"; font.pixelSize: 9; horizontalAlignment: Text.AlignLeft; LayoutMirroring.enabled: false }
                                        }
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: 17; color: "#0A100C"; border.color: window.border
                                        ColumnLayout {
                                            anchors.fill: parent; anchors.margins: 15; spacing: 8
                                            RowLayout {
                                                Layout.fillWidth: true
                                                ColumnLayout {
                                                    Layout.fillWidth: true; spacing: 2
                                                    Text { text: window.tr("رویدادهای اخیر", "RECENT EVENTS"); color: "#83A28E"; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 1 }
                                                    Text { text: window.tr("گزارش برنامه", "Application log"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 14; font.bold: true }
                                                }
                                                Text { text: "LOCAL LOG"; color: "#6F8977"; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 1 }
                                            }
                                            ScrollView {
                                                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                                                TextArea {
                                                    width: parent.width; text: bridge.diagnosticsText; readOnly: true; selectByMouse: true
                                                    wrapMode: TextEdit.Wrap; color: "#B5C9BA"; selectedTextColor: "#07110A"; selectionColor: window.green
                                                    font.family: "Consolas"; font.pixelSize: 9; background: null
                                                    LayoutMirroring.enabled: false
                                                    horizontalAlignment: TextEdit.AlignLeft
                                                }
                                            }
                                            Text { Layout.fillWidth: true; text: window.tr("گزارش‌ها به‌صورت محلی نگهداری می‌شوند.", "Logs remain on this device."); color: "#718578"; font.family: "Segoe UI"; font.pixelSize: 8 }
                                        }
                                    }
                                }
                            }
                        }

                        
                    }
                }
            }
        }
    }

    // Exit confirmation is custom-drawn to keep styling consistent and avoid native dialog chrome.
    Rectangle {
        anchors.fill: parent
        visible: window.dialogMode !== "" || opacity > 0.01
        opacity: window.dialogMode === "" ? 0 : 1
        scale: window.dialogMode === "" ? 0.985 : 1.0
        Behavior on opacity { NumberAnimation { duration: 170; easing.type: Easing.OutCubic } }
        Behavior on scale { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
        color: "#A6000000"
        z: 100
        MouseArea { anchors.fill: parent; onClicked: if (window.dialogMode !== "busy") window.dialogMode = "" }
        Rectangle {
            width: 390; height: window.dialogMode === "busy" ? 190 : 220
            anchors.centerIn: parent
            radius: 16; color: "#E1111B14"; border.color: "#34714A"
            scale: window.dialogMode === "" ? 0.975 : 1.0
            Behavior on scale { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
            Behavior on border.color { ColorAnimation { duration: 220 } }
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 20; spacing: 12
                Text { text: window.dialogMode === "busy" ? window.tr("عملیات در حال اجراست", "An operation is in progress") : window.tr("خروج از آچان", "Close Achan"); color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 15; font.bold: true }
                Text {
                    Layout.fillWidth: true
                    text: window.dialogMode === "busy" ? window.tr("لطفاً تا پایان اتصال یا قطع اتصال صبر کن. بستن اجباری ممکن است بازیابی شبکه را مختل کند.", "Wait until the connection operation finishes. Force-closing may prevent network restoration.") : window.tr("اتصال فعال است. ابتدا تونل به‌صورت کنترل‌شده قطع و سپس برنامه بسته می‌شود.", "A connection is active. The tunnel will be stopped safely before Achan closes.")
                    color: "#A9B9AE"; font.family: "Segoe UI"; font.pixelSize: 10; wrapMode: Text.WordWrap
                }
                Item { Layout.fillHeight: true }
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    Item { Layout.fillWidth: true }
                    ActionButton { label: window.dialogMode === "busy" ? window.tr("فهمیدم", "OK") : window.tr("انصراف", "Cancel"); accent: false; onClicked: window.dialogMode = "" }
                    ActionButton { visible: window.dialogMode !== "busy"; label: window.tr("قطع و خروج", "Disconnect & exit"); accent: true; onClicked: window.confirmClose() }
                }
            }
        }
    }

    SequentialAnimation {
        id: pageTransition
        NumberAnimation { target: pages; property: "opacity"; to: 0.12; duration: 105; easing.type: Easing.OutCubic }
        ScriptAction { script: window.currentPage = window.pendingPage }
        ParallelAnimation {
            NumberAnimation { target: pages; property: "opacity"; from: 0.12; to: 1.0; duration: 210; easing.type: Easing.OutCubic }
            NumberAnimation { target: pages; property: "scale"; from: 0.986; to: 1.0; duration: 210; easing.type: Easing.OutCubic }
        }
    }

    NumberAnimation {
        id: startupFade
        target: window
        property: "opacity"
        from: 0; to: 1; duration: 420
        easing.type: Easing.OutCubic
    }

    Component.onCompleted: {
        window.opacity = 0
        startupFade.start()
        particleField.initializeParticles()
    }

    Connections {
        target: bridge
        function onCloseReady() {
            window.allowClose = true
            closeFade.start()
        }
        function onStateChanged() {
            powerGlyph.requestPaint()
            powerRings.requestPaint()
            powerGlow.requestPaint()
            stateSpinner.requestPaint()
        }
    }

    NumberAnimation {
        id: closeFade
        target: window
        property: "opacity"
        from: 1; to: 0; duration: 190
        easing.type: Easing.OutCubic
        onFinished: {
            window.close()
            Qt.quit()
        }
    }

    // Native resize hit regions. Kept narrow so they do not cover titlebar controls.
    MouseArea { anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 5; z: 80; cursorShape: Qt.SizeHorCursor; onPressed: bridge.startSystemResize(Qt.LeftEdge) }
    MouseArea { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 5; z: 80; cursorShape: Qt.SizeHorCursor; onPressed: bridge.startSystemResize(Qt.RightEdge) }
    MouseArea { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 5; z: 80; cursorShape: Qt.SizeVerCursor; onPressed: bridge.startSystemResize(Qt.TopEdge) }
    MouseArea { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 5; z: 80; cursorShape: Qt.SizeVerCursor; onPressed: bridge.startSystemResize(Qt.BottomEdge) }

    component ProgressStep: ColumnLayout {
        id: progressStepRoot
        property string label: ""
        property string statusState: "idle"
        spacing: 2
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 4
            Rectangle {
                width: 6; height: 6; radius: 3
                color: progressStepRoot.statusState === "ready" ? window.green : progressStepRoot.statusState === "checking" ? "#E7B95E" : progressStepRoot.statusState === "error" ? "#F16A72" : "#627267"
                Layout.alignment: Qt.AlignVCenter
                property real pulseOpacity: 1.0
                opacity: progressStepRoot.statusState === "checking" ? pulseOpacity : 1.0
                scale: progressStepRoot.statusState === "checking" ? 1.25 : 1.0
                Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.InOutSine } }
                Behavior on color { ColorAnimation { duration: 300 } }
                Behavior on opacity { NumberAnimation { duration: 150 } }
                SequentialAnimation on pulseOpacity {
                    running: progressStepRoot.statusState === "checking"
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.42; duration: 430 }
                    NumberAnimation { to: 1.0; duration: 430 }
                }
            }
            Text {
                text: window.stageText(progressStepRoot.statusState)
                color: progressStepRoot.statusState === "ready" ? window.green : progressStepRoot.statusState === "checking" ? "#E7B95E" : progressStepRoot.statusState === "error" ? "#F18A91" : "#718177"
                font.family: "Segoe UI"
                font.pixelSize: 7
                font.bold: true
                Layout.alignment: Qt.AlignVCenter
                Behavior on color { ColorAnimation { duration: 300 } }
            }
        }
        Text {
            text: progressStepRoot.label
            color: progressStepRoot.statusState === "ready" ? "#B9D9C2" : progressStepRoot.statusState === "checking" ? "#DCC58F" : progressStepRoot.statusState === "error" ? "#E79BA0" : "#829287"
            font.family: "Segoe UI"
            font.pixelSize: 8
            Layout.alignment: Qt.AlignHCenter
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }
    }

    component WindowControl: Rectangle {
        id: controlRoot
        property string kind: "minimize"
        property bool isClose: false
        onKindChanged: Qt.callLater(function() { controlIcon.requestPaint() })
        onIsCloseChanged: Qt.callLater(function() { controlIcon.requestPaint() })
        signal clicked()
        width: 38; height: 34; radius: 8
        color: mouse.containsMouse ? (isClose ? "#8F2930" : "#1D3023") : "transparent"
        border.color: mouse.containsMouse ? (isClose ? "#CA4A53" : "#315C40") : "transparent"
        scale: mouse.pressed ? 0.93 : mouse.containsMouse ? 1.07 : 1.0
        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }
        Canvas {
            id: controlIcon
            anchors.centerIn: parent; width: 18; height: 18
            onPaint: {
                var c = getContext("2d")
                c.clearRect(0, 0, width, height)
                c.strokeStyle = controlRoot.isClose ? "#F4F7F4" : "#D6E2D9"
                c.lineWidth = 1.8
                c.lineCap = "square"
                if (controlRoot.kind === "minimize") {
                    c.beginPath(); c.moveTo(3, 10); c.lineTo(15, 10); c.stroke()
                } else if (controlRoot.kind === "maximize") {
                    c.strokeRect(3.5, 3.5, 11, 11)
                } else if (controlRoot.kind === "restore") {
                    c.strokeRect(5.5, 3, 10, 10)
                    c.fillStyle = "#0C140F"; c.fillRect(2, 6, 10, 10)
                    c.strokeRect(2.5, 6.5, 10, 10)
                } else {
                    c.beginPath(); c.moveTo(4, 4); c.lineTo(14, 14); c.moveTo(14, 4); c.lineTo(4, 14); c.stroke()
                }
            }
        }
        MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: controlRoot.clicked() }
    }

    component NavItem: Rectangle {
        id: navRoot
        property string label: ""
        property string glyph: ""
        property bool selected: false
        signal clicked()
        implicitHeight: 43
        radius: 10
        color: selected ? "#173A25" : mouse.containsMouse ? "#14251A" : "transparent"
        border.width: selected ? 1 : 0
        border.color: selected ? "#2D7447" : mouse.containsMouse ? "#284B34" : "transparent"
        scale: mouse.pressed ? 0.985 : mouse.containsMouse ? 1.018 : 1.0
        Behavior on scale { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 180 } }
        Behavior on border.color { ColorAnimation { duration: 180 } }
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 11; anchors.rightMargin: 11; spacing: 10
            Text {
                text: navRoot.glyph
                color: navRoot.selected ? window.green : mouse.containsMouse ? "#B5F5C9" : "#8CA094"
                font.family: "Segoe UI Symbol"
                font.pixelSize: 17
                Behavior on color { ColorAnimation { duration: 160 } }
                Layout.alignment: Qt.AlignVCenter
            }
            Text {
                text: navRoot.label
                color: navRoot.selected ? "#EAF5ED" : mouse.containsMouse ? "#D5E8D9" : "#A9B8AE"
                font.family: "Segoe UI"
                font.pixelSize: 11
                Behavior on color { ColorAnimation { duration: 160 } }
                Layout.fillWidth: true
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: bridge.language === "fa" ? Text.AlignRight : Text.AlignLeft
                elide: Text.ElideRight
            }
        }
        MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: navRoot.clicked() }
    }

    component BottomNavItem: Rectangle {
        id: bottomNavRoot
        property string label: ""
        property string glyph: ""
        property bool selected: false
        signal clicked()
        implicitHeight: 54
        radius: 10
        color: selected ? "#173A25" : mouse.containsMouse ? "#14251A" : "transparent"
        border.width: selected ? 1 : 0
        border.color: selected ? "#2D7447" : "transparent"
        Behavior on color { ColorAnimation { duration: 180 } }
        Behavior on border.color { ColorAnimation { duration: 180 } }
        Column {
            anchors.centerIn: parent
            spacing: 2
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: bottomNavRoot.glyph
                color: bottomNavRoot.selected ? window.green : mouse.containsMouse ? "#B5F5C9" : "#8CA094"
                font.family: "Segoe UI Symbol"
                font.pixelSize: 17
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: bottomNavRoot.label
                color: bottomNavRoot.selected ? "#EAF5ED" : mouse.containsMouse ? "#D5E8D9" : "#A9B8AE"
                font.family: "Segoe UI"
                font.pixelSize: 10
                elide: Text.ElideRight
            }
        }
        MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bottomNavRoot.clicked() }
    }

    component DashboardMetric: Rectangle {
        id: dashboardMetricRoot
        property string label: ""
        property string value: ""
        property string glyph: ""
        property bool active: false
        Layout.fillWidth: true; Layout.preferredHeight: 52
        radius: 10; color: "#101D14"; border.color: "#1C3022"
        RowLayout {
            anchors.fill: parent; anchors.margins: 8; spacing: 7
            Text { text: dashboardMetricRoot.glyph; color: "#77AA86"; font.family: "Segoe UI Symbol"; font.pixelSize: 16 }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 2
                Text { Layout.fillWidth: true; text: dashboardMetricRoot.label; color: "#819588"; font.family: "Segoe UI"; font.pixelSize: 8; elide: Text.ElideRight }
                Text { Layout.fillWidth: true; text: dashboardMetricRoot.value; color: "#B8C9BD"; font.family: dashboardMetricRoot.value.length > 16 ? "Segoe UI" : "Consolas"; font.pixelSize: 9; elide: Text.ElideRight; LayoutMirroring.enabled: false; horizontalAlignment: Text.AlignLeft }
            }
            Rectangle { width: 6; height: 6; radius: 3; color: dashboardMetricRoot.active ? window.green : "#4B5C50"; Layout.alignment: Qt.AlignTop }
        }
    }

    component DiagnosticRow: RowLayout {
        id: diagnosticRowRoot
        property string labelText: ""
        property string valueText: ""
        property string stateValue: "idle"
        Layout.fillWidth: true; Layout.preferredHeight: 38
        Rectangle {
            width: 7; height: 7; radius: 4; Layout.alignment: Qt.AlignVCenter
            color: diagnosticRowRoot.stateValue === "ready" ? window.green : diagnosticRowRoot.stateValue === "checking" ? "#E7B95E" : diagnosticRowRoot.stateValue === "error" ? "#E56B76" : "#536357"
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 2
            Text { text: diagnosticRowRoot.labelText; color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 10; font.bold: true }
            Text { text: diagnosticRowRoot.valueText; color: diagnosticRowRoot.stateValue === "error" ? "#E7838A" : "#839588"; font.family: "Segoe UI"; font.pixelSize: 8 }
        }
    }

    component StatusPill: Rectangle {
        width: 104; height: 30; radius: 10
        color: bridge.isConnected ? "#153A25" : bridge.isBusy ? "#392E19" : "#32191D"
        border.color: bridge.isConnected ? "#2D8650" : bridge.isBusy ? "#80662F" : "#84404A"
        Behavior on color { ColorAnimation { duration: 320 } }
        Behavior on border.color { ColorAnimation { duration: 320 } }
        Row {
            anchors.centerIn: parent; spacing: 7
            Rectangle { width: 7; height: 7; radius: 4; anchors.verticalCenter: parent.verticalCenter; color: window.connectionAccent() }
            Text { text: window.stateText(); color: window.connectionAccent(); font.family: "Segoe UI"; font.pixelSize: 9; font.bold: true }
        }
    }




    component PageHeading: RowLayout {
        property string eyebrowText: ""
        property string titleText: ""
        property string subtitleText: ""
        Layout.fillWidth: true; Layout.preferredHeight: 54
        Column {
            spacing: 1
            Text { text: parent.parent.eyebrowText; color: "#83A28E"; font.family: "Segoe UI"; font.pixelSize: 8; font.letterSpacing: 1; visible: text.length > 0 }
            Text { text: parent.parent.titleText; color: window.textPrimary; font.family: "Segoe UI"; font.pixelSize: 21; font.bold: true }
            Text { text: parent.parent.subtitleText; color: window.textMuted; font.family: "Segoe UI"; font.pixelSize: 10 }
        }
    }
    component InfoRow: RowLayout {
        property string label: ""
        property string value: ""
        spacing: 12
        Layout.fillWidth: true
        Layout.preferredHeight: 28
        Text {
            text: parent.label
            color: "#91A397"
            font.family: "Segoe UI"
            font.pixelSize: 10
            Layout.fillWidth: true
            horizontalAlignment: bridge.language === "fa" ? Text.AlignRight : Text.AlignLeft
        }
        Text {
            text: parent.value
            color: window.textPrimary
            font.family: "Segoe UI"
            font.pixelSize: 10
            font.bold: true
            LayoutMirroring.enabled: false
            horizontalAlignment: bridge.language === "fa" ? Text.AlignLeft : Text.AlignRight
        }
    }

    component DividerLine: Rectangle { Layout.fillWidth: true; height: 1; color: "#26382D" }

    component SmallButton: Rectangle {
        property string label: ""
        property bool selected: false
        signal clicked()
        width: 96; height: 34; radius: 9
        color: selected ? "#174127" : mouse.containsMouse ? "#182C1E" : "#111C14"
        border.color: selected ? "#348853" : mouse.containsMouse ? "#4C815B" : "#304738"
        scale: mouse.pressed ? 0.96 : mouse.containsMouse ? 1.035 : 1.0
        Behavior on scale { NumberAnimation { duration: 125; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 160 } }
        Behavior on border.color { ColorAnimation { duration: 160 } }
        Text { anchors.centerIn: parent; text: parent.label; color: parent.selected ? window.green : "#BBC9BF"; font.family: "Segoe UI"; font.pixelSize: 10; font.bold: parent.selected }
        MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: parent.clicked() }
    }

    component ActionButton: Rectangle {
        property string label: ""
        property bool accent: false
        signal clicked()
        implicitWidth: Math.max(110, buttonText.implicitWidth + 28)
        height: 36; radius: 9
        color: !enabled ? "#172019" : accent ? (mouse.containsMouse ? "#2CBF69" : "#1B8E4B") : (mouse.containsMouse ? "#1B3021" : "#142019")
        border.color: accent ? (mouse.containsMouse ? "#72F5A2" : "#39C875") : (mouse.containsMouse ? "#5B8066" : "#385343")
        opacity: enabled ? 1 : 0.48
        scale: mouse.pressed ? 0.965 : mouse.containsMouse ? 1.025 : 1.0
        Behavior on scale { NumberAnimation { duration: 125; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 160 } }
        Behavior on border.color { ColorAnimation { duration: 160 } }
        Text { id: buttonText; anchors.centerIn: parent; text: parent.label; color: "#F0F8F2"; font.family: "Segoe UI"; font.pixelSize: 10; font.bold: true }
        MouseArea { id: mouse; anchors.fill: parent; enabled: parent.enabled; hoverEnabled: true; cursorShape: parent.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor; onClicked: parent.clicked() }
    }

}
