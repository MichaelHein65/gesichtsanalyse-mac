#!/bin/zsh
set -e

cd "${0:A:h}"

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r python_app/requirements.txt

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js/npm fehlt. Bitte Node.js installieren und Setup erneut starten."
  exit 1
fi

npm install --prefix web3d --no-audit --no-fund
mkdir -p web3d/vendor
cp web3d/node_modules/three/build/three.module.js web3d/vendor/three.module.js
cp web3d/node_modules/three/build/three.core.js web3d/vendor/three.core.js

mkdir -p models
if [[ ! -f models/face_landmarker.task ]]; then
  curl --proto '=https' --tlsv1.2 --fail --location \
    --output models/face_landmarker.task \
    'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
fi

./build_macos_app.command

echo "Installation abgeschlossen. Start im Finder mit Gesichtsanalyse.app"
