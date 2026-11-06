import * as THREE from '/vendor/three.module.js';

const stage = document.querySelector('#stage');
const statusElement = document.querySelector('#status');
const statusText = document.querySelector('#statusText');
const fpsElement = document.querySelector('#fps');
const recordButton = document.querySelector('#recordButton');
const closeButton = document.querySelector('#closeButton');

const clamp = (value, low = 0, high = 1) => Math.min(high, Math.max(low, value || 0));
const average = (...values) => values.reduce((sum, value) => sum + value, 0) / values.length;
const radians = THREE.MathUtils.degToRad;
const expression = (name) => clamp(tracking.blendshapes[name]);

const tracking = {
  face: false,
  pose: { yaw: 0, pitch: 0, roll: 0 },
  blendshapes: {},
  receivedAt: 0,
};

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x170d25, 0.047);

const camera = new THREE.PerspectiveCamera(33, innerWidth / innerHeight, 0.1, 100);
camera.position.set(0, 0.05, 11.25);
camera.lookAt(0, -0.18, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.16;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
stage.appendChild(renderer.domElement);

scene.add(new THREE.HemisphereLight(0xffd2c2, 0x15203b, 1.8));
const keyLight = new THREE.DirectionalLight(0xffe0ca, 4.2);
keyLight.position.set(-4.5, 6, 6);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(2048, 2048);
keyLight.shadow.camera.left = -5;
keyLight.shadow.camera.right = 5;
keyLight.shadow.camera.top = 6;
keyLight.shadow.camera.bottom = -5;
scene.add(keyLight);
const rimLight = new THREE.PointLight(0x62e5d8, 38, 13, 2);
rimLight.position.set(4.7, 2.6, 2.0);
scene.add(rimLight);
const hairLight = new THREE.PointLight(0xff658b, 25, 11, 2);
hairLight.position.set(-4.2, 1.3, -1.5);
scene.add(hairLight);

const materials = {
  skin: new THREE.MeshPhysicalMaterial({ color: 0xefad8d, roughness: 0.57, metalness: 0.0, clearcoat: 0.12, clearcoatRoughness: 0.72 }),
  skinShadow: new THREE.MeshStandardMaterial({ color: 0xd98870, roughness: 0.78 }),
  hair: new THREE.MeshPhysicalMaterial({ color: 0x6f251d, roughness: 0.42, clearcoat: 0.32, clearcoatRoughness: 0.48 }),
  hairLight: new THREE.MeshPhysicalMaterial({ color: 0xa74328, roughness: 0.38, clearcoat: 0.4, clearcoatRoughness: 0.4 }),
  white: new THREE.MeshPhysicalMaterial({ color: 0xfffbf4, roughness: 0.25, clearcoat: 0.28 }),
  iris: new THREE.MeshPhysicalMaterial({ color: 0x103f3b, roughness: 0.18, clearcoat: 1.0 }),
  pupil: new THREE.MeshBasicMaterial({ color: 0x080b13 }),
  lip: new THREE.MeshPhysicalMaterial({ color: 0xc7475f, roughness: 0.38, clearcoat: 0.45 }),
  mouth: new THREE.MeshStandardMaterial({ color: 0x421522, roughness: 0.6 }),
  teeth: new THREE.MeshStandardMaterial({ color: 0xfff3e6, roughness: 0.4 }),
  hoodie: new THREE.MeshPhysicalMaterial({ color: 0xd95452, roughness: 0.72, sheen: 0.7, sheenColor: new THREE.Color(0xff9a82) }),
  hoodieDark: new THREE.MeshStandardMaterial({ color: 0x8e2f3b, roughness: 0.82 }),
  blush: new THREE.MeshBasicMaterial({ color: 0xe76f6d, transparent: true, opacity: 0.11, depthWrite: false }),
  mesh: new THREE.MeshBasicMaterial({ color: 0x72f0da, transparent: true, opacity: 0.9 }),
};

const root = new THREE.Group();
root.position.y = 0.12;
scene.add(root);

const bust = new THREE.Group();
root.add(bust);

function mesh(geometry, material, position, scale = [1, 1, 1], rotation = [0, 0, 0], parent = root) {
  const object = new THREE.Mesh(geometry, material);
  object.position.set(...position);
  object.scale.set(...scale);
  object.rotation.set(...rotation);
  object.castShadow = true;
  object.receiveShadow = true;
  parent.add(object);
  return object;
}

const torso = mesh(new THREE.SphereGeometry(1, 48, 32), materials.hoodie, [0, -2.05, -0.1], [1.56, 1.08, 0.78], [0, 0, 0], bust);
mesh(new THREE.TorusGeometry(0.62, 0.145, 16, 64, Math.PI * 1.55), materials.hoodieDark, [0, -1.47, 0.54], [1, 0.82, 1], [0.25, 0, -0.86], bust);
mesh(new THREE.CylinderGeometry(0.29, 0.34, 0.72, 32), materials.skinShadow, [0, -0.94, -0.04], [1, 1, 1], [0, 0, 0], bust);
for (const x of [-0.29, 0.29]) {
  mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.76, 12), materials.white, [x, -1.69, 0.86], [1, 1, 1], [0.06, 0, x > 0 ? -0.1 : 0.1], bust);
  mesh(new THREE.SphereGeometry(0.052, 16, 12), materials.white, [x + (x > 0 ? 0.04 : -0.04), -2.06, 0.88], [1, 1.25, 1], [0, 0, 0], bust);
}

const head = new THREE.Group();
head.position.y = 0.58;
root.add(head);

// Hair volume first, so the skin and facial elements sit naturally in front of it.
mesh(new THREE.SphereGeometry(1, 64, 48), materials.hair, [0, 0.03, -0.24], [1.47, 1.73, 1.05], [0, 0, 0], head);
mesh(new THREE.SphereGeometry(1, 64, 48), materials.skin, [0, -0.04, 0.12], [1.24, 1.46, 1.04], [0, 0, 0], head);

// Ears and earrings.
for (const side of [-1, 1]) {
  mesh(new THREE.SphereGeometry(0.29, 32, 24), materials.skinShadow, [side * 1.18, -0.04, 0.0], [0.62, 1, 0.45], [0, 0, 0], head);
  mesh(new THREE.TorusGeometry(0.09, 0.018, 10, 30), materials.mesh, [side * 1.28, -0.42, 0.02], [1, 1, 1], [0, 0, 0], head);
}

// Sculpted front locks: layered ellipsoids give the hair the icon's dimensional sweep.
const locks = [
  [-0.78, 1.09, 0.58, 0.48, 0.93, 0.38, -0.18, 0.04, -0.42],
  [-0.2, 1.36, 0.49, 0.48, 0.72, 0.34, -0.08, 0.12, -0.18],
  [0.44, 1.27, 0.42, 0.52, 0.84, 0.36, 0.08, -0.05, 0.28],
  [0.89, 0.91, 0.29, 0.42, 0.92, 0.32, 0.18, -0.02, 0.42],
  [-1.08, 0.38, 0.2, 0.34, 1.08, 0.3, -0.1, 0.05, -0.15],
  [1.12, 0.28, 0.08, 0.31, 1.18, 0.31, 0.08, -0.03, 0.14],
];
locks.forEach(([x, y, z, sx, sy, sz, rx, ry, rz], index) => {
  mesh(new THREE.SphereGeometry(1, 36, 24), index % 2 ? materials.hairLight : materials.hair, [x, y, z], [sx, sy, sz], [rx, ry, rz], head);
});

const eyes = {};
for (const [name, side] of [['left', -1], ['right', 1]]) {
  const eye = new THREE.Group();
  eye.position.set(side * 0.47, 0.24, 1.0);
  head.add(eye);
  const sclera = mesh(new THREE.SphereGeometry(1, 40, 24), materials.white, [0, 0, 0], [0.34, 0.205, 0.13], [0, 0, 0], eye);
  const iris = mesh(new THREE.SphereGeometry(1, 32, 20), materials.iris, [0, 0, 0.122], [0.105, 0.105, 0.035], [0, 0, 0], eye);
  const pupil = mesh(new THREE.SphereGeometry(1, 24, 16), materials.pupil, [0, 0, 0.153], [0.047, 0.047, 0.017], [0, 0, 0], eye);
  mesh(new THREE.SphereGeometry(1, 12, 8), materials.white, [-0.026, 0.032, 0.172], [0.018, 0.018, 0.008], [0, 0, 0], eye);
  eyes[name] = { group: eye, sclera, iris, pupil };
}

// Brows are rebuilt only when their curvature changes materially.
const brows = { left: new THREE.Group(), right: new THREE.Group() };
head.add(brows.left, brows.right);
function updateBrow(group, side, lift, down, force = false) {
  const state = `${Math.round(lift * 20)}:${Math.round(down * 20)}`;
  if (!force && group.userData.state === state) return;
  group.userData.state = state;
  group.children.forEach((child) => child.geometry.dispose());
  group.clear();
  const y = 0.62 + lift * 0.18 - down * 0.12;
  const points = [
    new THREE.Vector3(side * 0.23, y + lift * 0.06, 1.12),
    new THREE.Vector3(side * 0.48, y + 0.07 - down * 0.04, 1.17),
    new THREE.Vector3(side * 0.76, y - 0.02 + lift * 0.04, 1.08),
  ];
  const brow = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 20, 0.045, 8, false), materials.hair);
  brow.castShadow = true;
  group.add(brow);
}
updateBrow(brows.left, -1, 0, 0, true);
updateBrow(brows.right, 1, 0, 0, true);

mesh(new THREE.SphereGeometry(1, 32, 24), materials.skinShadow, [0, -0.02, 1.115], [0.12, 0.26, 0.15], [0.06, 0, 0], head);
mesh(new THREE.SphereGeometry(1, 24, 18), materials.skin, [0, -0.18, 1.22], [0.155, 0.095, 0.105], [0, 0, 0], head);

const leftCheek = mesh(new THREE.CircleGeometry(0.16, 32), materials.blush, [-0.70, -0.29, 1.092], [1, 0.62, 1], [0, 0, 0], head);
const rightCheek = mesh(new THREE.CircleGeometry(0.16, 32), materials.blush, [0.70, -0.29, 1.092], [1, 0.62, 1], [0, 0, 0], head);
leftCheek.castShadow = false;
rightCheek.castShadow = false;

const mouthGroup = new THREE.Group();
mouthGroup.position.set(0, -0.63, 1.04);
head.add(mouthGroup);
const mouthCavity = mesh(new THREE.SphereGeometry(1, 40, 24), materials.mouth, [0, 0, 0], [0.43, 0.055, 0.09], [0, 0, 0], mouthGroup);
const teeth = mesh(new THREE.BoxGeometry(1, 1, 1, 8, 2, 1), materials.teeth, [0, 0.045, 0.078], [0.49, 0.035, 0.035], [0, 0, 0], mouthGroup);
const lips = { upper: new THREE.Group(), lower: new THREE.Group() };
mouthGroup.add(lips.upper, lips.lower);

function updateLips(smile, frown, pucker, open, force = false) {
  const state = [smile, frown, pucker, open].map((value) => Math.round(value * 20)).join(':');
  if (!force && mouthGroup.userData.state === state) return;
  mouthGroup.userData.state = state;
  const width = 0.44 - pucker * 0.20;
  const corner = smile * 0.16 - frown * 0.13;
  const gap = open * 0.18;
  const configurations = [
    [lips.upper, [new THREE.Vector3(-width, corner, 0.10), new THREE.Vector3(0, 0.07 + gap * 0.2, 0.14), new THREE.Vector3(width, corner, 0.10)], 0.045],
    [lips.lower, [new THREE.Vector3(-width, corner - gap, 0.10), new THREE.Vector3(0, -0.06 - gap, 0.14), new THREE.Vector3(width, corner - gap, 0.10)], 0.052],
  ];
  configurations.forEach(([group, points, radius]) => {
    group.children.forEach((child) => child.geometry.dispose());
    group.clear();
    const lip = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 30, radius, 10, false), materials.lip);
    lip.castShadow = true;
    group.add(lip);
  });
}
updateLips(0, 0, 0, 0, true);

// A restrained mint landmark sculpture echoes the app icon without hiding the face.
const faceMesh = new THREE.Group();
faceMesh.visible = false;
head.add(faceMesh);
const meshPoints = [
  [0.05, 1.06, 0.98], [0.42, 0.93, 0.98], [0.73, 0.66, 0.94], [0.91, 0.27, 0.9],
  [0.94, -0.16, 0.83], [0.82, -0.59, 0.77], [0.58, -0.96, 0.73], [0.22, -1.18, 0.72],
  [0.14, 0.52, 1.13], [0.52, 0.46, 1.12], [0.73, 0.23, 1.04], [0.18, 0.08, 1.25],
  [0.58, -0.10, 1.09], [0.18, -0.38, 1.17], [0.55, -0.55, 1.03], [0.24, -0.78, 0.98],
];
const meshConnections = [[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,7],[0,8],[8,9],[9,2],[8,11],[9,10],[10,3],[11,12],[12,10],[11,13],[12,14],[13,14],[13,15],[14,15],[15,6],[15,7],[2,10],[4,12],[5,14]];
const linePositions = [];
meshConnections.forEach(([a, b]) => linePositions.push(...meshPoints[a], ...meshPoints[b]));
const lineGeometry = new THREE.BufferGeometry();
lineGeometry.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
const meshLines = new THREE.LineSegments(lineGeometry, new THREE.LineBasicMaterial({ color: 0x6cf4dd, transparent: true, opacity: 0.7 }));
faceMesh.add(meshLines);
meshPoints.forEach((point) => {
  const landmark = mesh(new THREE.SphereGeometry(0.027, 12, 8), materials.mesh, point, [1, 1, 1], [0, 0, 0], faceMesh);
  landmark.castShadow = false;
});

// Ground reflection/shadow and slow ambient particles complete the studio scene.
const floor = mesh(new THREE.CircleGeometry(3.1, 64), new THREE.MeshStandardMaterial({ color: 0x170e25, roughness: 0.58, metalness: 0.25, transparent: true, opacity: 0.72 }), [0, -3.37, 0], [1, 1, 1], [-Math.PI / 2, 0, 0], scene);
floor.receiveShadow = true;
const particlesGeometry = new THREE.BufferGeometry();
const particlePositions = [];
for (let i = 0; i < 85; i += 1) particlePositions.push((Math.random() - .5) * 14, (Math.random() - .4) * 9, (Math.random() - .5) * 7 - 1.5);
particlesGeometry.setAttribute('position', new THREE.Float32BufferAttribute(particlePositions, 3));
const particles = new THREE.Points(particlesGeometry, new THREE.PointsMaterial({ color: 0xffb49d, size: 0.024, transparent: true, opacity: 0.42, depthWrite: false }));
scene.add(particles);

function setMetric(name, value) {
  const percent = Math.round(clamp(value) * 100);
  document.querySelector(`#${name}Bar`).style.width = `${percent}%`;
  document.querySelector(`#${name}Value`).textContent = `${percent}%`;
}

async function toggleRecording() {
  if (!window.pywebview?.api) return;
  const result = await window.pywebview.api.toggle_recording();
  recordButton.classList.toggle('recording', result.active);
  recordButton.firstChild.textContent = result.active ? 'Aufnahme läuft ' : 'Aufnehmen ';
}
recordButton.addEventListener('click', toggleRecording);
closeButton.addEventListener('click', () => window.pywebview?.api?.close());
addEventListener('keydown', (event) => {
  if (event.key.toLowerCase() === 'r') toggleRecording();
  if (event.key.toLowerCase() === 'q' || event.key === 'Escape') window.pywebview?.api?.close();
});

function connect() {
  const socket = new WebSocket(`ws://${location.host}/ws`);
  socket.addEventListener('message', ({ data }) => {
    const message = JSON.parse(data);
    if (message.type === 'error') {
      statusElement.className = 'glass status error';
      statusText.textContent = message.message;
      return;
    }
    if (message.type !== 'tracking') return;
    tracking.face = message.face;
    tracking.receivedAt = performance.now();
    if (message.pose) tracking.pose = message.pose;
    if (message.blendshapes) tracking.blendshapes = message.blendshapes;
    fpsElement.textContent = `${message.fps || 0} FPS`;
    statusElement.className = `glass status${message.face ? ' live' : ''}`;
    statusText.textContent = message.face ? 'Gesicht aktiv' : 'Schau in die Kamera';
  });
  socket.addEventListener('close', () => {
    statusElement.className = 'glass status error';
    statusText.textContent = 'Verbindung wird erneuert …';
    setTimeout(connect, 700);
  });
}
connect();

let lastTime = performance.now();
function animate(now) {
  requestAnimationFrame(animate);
  const delta = Math.min((now - lastTime) / 1000, 0.05);
  lastTime = now;
  const time = now / 1000;
  const hasFace = tracking.face && now - tracking.receivedAt < 900;
  const response = 1 - Math.pow(0.001, delta);

  const targetYaw = hasFace ? radians(-tracking.pose.yaw * 0.85) : Math.sin(time * 0.45) * 0.045;
  const targetPitch = hasFace ? radians(tracking.pose.pitch * 0.72) : Math.sin(time * 0.6) * 0.018;
  const targetRoll = hasFace ? radians(-tracking.pose.roll * 0.8) : Math.sin(time * 0.38) * 0.025;
  head.rotation.y = THREE.MathUtils.lerp(head.rotation.y, targetYaw, response);
  head.rotation.x = THREE.MathUtils.lerp(head.rotation.x, targetPitch, response);
  head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, targetRoll, response);

  const blinkLeft = hasFace ? expression('eyeBlinkLeft') : 0;
  const blinkRight = hasFace ? expression('eyeBlinkRight') : 0;
  const lookX = hasFace ? (expression('eyeLookOutRight') + expression('eyeLookInLeft') - expression('eyeLookOutLeft') - expression('eyeLookInRight')) * 0.5 : Math.sin(time * 0.72) * 0.12;
  const lookY = hasFace ? (expression('eyeLookUpLeft') + expression('eyeLookUpRight') - expression('eyeLookDownLeft') - expression('eyeLookDownRight')) * 0.35 : 0;
  [['left', blinkLeft], ['right', blinkRight]].forEach(([name, blink]) => {
    const eye = eyes[name];
    eye.group.scale.y = THREE.MathUtils.lerp(eye.group.scale.y, Math.max(0.07, 1 - blink * 0.96), response);
    eye.iris.position.x = lookX * 0.09;
    eye.pupil.position.x = lookX * 0.09;
    eye.iris.position.y = lookY * 0.075;
    eye.pupil.position.y = lookY * 0.075;
  });

  const smile = average(expression('mouthSmileLeft'), expression('mouthSmileRight'));
  const frown = average(expression('mouthFrownLeft'), expression('mouthFrownRight'));
  const open = expression('jawOpen');
  const pucker = Math.max(expression('mouthPucker'), expression('mouthFunnel'));
  const browLift = Math.max(expression('browInnerUp'), average(expression('browOuterUpLeft'), expression('browOuterUpRight')));
  const browDownLeft = expression('browDownLeft');
  const browDownRight = expression('browDownRight');
  const cheek = expression('cheekPuff');

  updateBrow(brows.left, -1, Math.max(browLift, expression('browOuterUpLeft')), browDownLeft);
  updateBrow(brows.right, 1, Math.max(browLift, expression('browOuterUpRight')), browDownRight);
  updateLips(smile, frown, pucker, open);
  mouthCavity.scale.x = THREE.MathUtils.lerp(mouthCavity.scale.x, 0.43 - pucker * 0.18, response);
  mouthCavity.scale.y = THREE.MathUtils.lerp(mouthCavity.scale.y, 0.045 + open * 0.29 + pucker * 0.09, response);
  teeth.visible = open > 0.13 && pucker < 0.65;
  teeth.scale.y = 0.025 + open * 0.055;
  leftCheek.scale.x = THREE.MathUtils.lerp(leftCheek.scale.x, 1 + cheek * 0.22 + smile * 0.08, response);
  rightCheek.scale.x = THREE.MathUtils.lerp(rightCheek.scale.x, 1 + cheek * 0.22 + smile * 0.08, response);

  const breath = Math.sin(time * 1.65) * 0.012;
  torso.scale.y = 1.08 * (1 + breath);
  bust.position.y = breath * 0.8;
  particles.rotation.y = time * 0.018;
  faceMesh.children.forEach((child, index) => {
    if (child.isMesh) child.material.opacity = 0.72 + Math.sin(time * 2.1 + index * 0.7) * 0.18;
  });

  setMetric('smile', smile);
  setMetric('jaw', open);
  setMetric('brow', browLift);
  setMetric('blink', average(blinkLeft, blinkRight));
  renderer.render(scene, camera);
}
requestAnimationFrame(animate);

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
});
