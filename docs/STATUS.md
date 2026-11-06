# Projektstatus

Stand: 6. November 2026

## Funktionsfähig

- Zugriff auf FaceTime- und weitere macOS-Kameras
- MediaPipe Face Landmarker mit 478 dreidimensionalen Landmarken
- 52 Blendshape-Werte für mimische Bewegungen
- Kopfpose als Yaw, Pitch und Roll
- geglättete Echtzeitsteuerung eines beleuchteten Three.js-Avatars
- Augen, Blickrichtung, Augenbrauen, Lippen, Kiefer und Kopfbewegung
- 3D-Avatar ohne eingeblendetes Tracking-Gitter
- lokale JSONL-Aufzeichnung auf ausdrücklichen Start
- nativer macOS-Launcher mit eigenem Icon und ohne Terminalfenster
- gemeinsames Beenden von Kamera, Tracker, WebView und lokalem Server

## Verifiziert

- praktischer App-Start mit Live-Kamera bei ungefähr 30 Bildern pro Sekunde
- macOS-Kamerafreigabe unter der App-Identität `de.michaelhein.gesichtsanalyse`
- Ad-hoc-Codesignatur und gültige `Info.plist`
- neun automatisierte Python-Tests, darunter die AVFoundation-Blocksignatur
- expliziter Server-Lifecycle-Test mit Portfreigabe

## Mögliche nächste Schritte

- mehrere auswählbare Avatar-Modelle
- Kalibrierung einer persönlichen Neutralpose
- Export zusammengefasster Mimik-Metriken
- signierte und notarisierte Release-Builds für andere Macs
- optionale Video- oder Alpha-Ausgabe für Streaming-Software

## Abgrenzung

Die Anwendung misst Gesichtsbewegungen. Sie behauptet nicht, komplexe Emotionen, Absichten oder psychische Zustände zuverlässig zu erkennen. Für medizinische, diagnostische oder sicherheitskritische Einsätze ist eine gesonderte Validierung erforderlich.
