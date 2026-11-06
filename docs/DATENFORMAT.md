# Aufzeichnungsformat und Datenschutz

Eine Aufzeichnung beginnt nur nach Betätigung von `R` oder „Aufnehmen“. Sie wird als JSON Lines im lokalen, von Git ignorierten Ordner `output/` gespeichert. Pro verarbeitetem Kamerabild entsteht genau eine JSON-Zeile.

## Struktur einer Zeile

```json
{
  "timestamp_ms": 1234,
  "head_pose_degrees": {
    "yaw": 4.25,
    "pitch": -2.1,
    "roll": 0.8
  },
  "blendshapes": {
    "eyeBlinkLeft": 0.02,
    "jawOpen": 0.31,
    "mouthSmileLeft": 0.64
  },
  "landmarks": [
    {"index": 0, "x": 0.51, "y": 0.42, "z": -0.03}
  ]
}
```

## Koordinaten und Werte

- `timestamp_ms`: Millisekunden seit Start der laufenden Sitzung
- `yaw`, `pitch`, `roll`: geglättete Kopfdrehung in Grad
- `blendshapes`: MediaPipe-Werte im typischen Bereich von 0 bis 1
- `landmarks`: alle 478 geglätteten Punkte mit normierten Bildkoordinaten

## Datenschutz

- Es erfolgt keine Netzwerkübertragung an externe Hosts.
- Der interne Server lauscht nur auf `127.0.0.1`.
- Kamerabilder werden standardmäßig weder gespeichert noch an die 3D-Oberfläche gesendet.
- JSONL-Daten können biometrische Bewegungsmuster enthalten und sollten entsprechend geschützt werden.
- `output/` und `*.jsonl` sind in `.gitignore` ausgeschlossen.
