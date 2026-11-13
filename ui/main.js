import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const EARTH_RADIUS_KM = 6371;
const POSITION_POLL_MS = 2000;
const TRACK_REFRESH_MS = 60000;

const select = document.getElementById("satellite-select");
const addForm = document.getElementById("add-form");
const noradInput = document.getElementById("norad-input");
const removeBtn = document.getElementById("remove-btn");
const message = document.getElementById("message");


const container = document.getElementById("globe");
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.01, 100);
camera.position.set(0, 1.5, 3.5);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enablePan = false;
controls.minDistance = 1.5;
controls.maxDistance = 8;

scene.add(new THREE.AmbientLight(0xffffff, 0.9));
const sun = new THREE.DirectionalLight(0xffffff, 1.2);
sun.position.set(5, 3, 5);
scene.add(sun);

const earthMaterial = new THREE.MeshPhongMaterial({ color: 0x1d4e89 });
const earth = new THREE.Mesh(new THREE.SphereGeometry(1, 64, 64), earthMaterial);
scene.add(earth);

new THREE.TextureLoader().load(
  "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r160/examples/textures/planets/earth_atmos_2048.jpg",
  (texture) => {
    texture.colorSpace = THREE.SRGBColorSpace;
    earthMaterial.map = texture;
    earthMaterial.color.set(0xffffff);
    earthMaterial.needsUpdate = true;
  },
  undefined,
  () => console.warn("Earth texture failed to load, using plain blue sphere")
);

const marker = new THREE.Mesh(
  new THREE.SphereGeometry(0.02, 16, 16),
  new THREE.MeshBasicMaterial({ color: 0xffd23f })
);
marker.visible = false;
scene.add(marker);

let orbitLine = null;

// Turns latitude/longitude/altitude into a point in the scene.
// The Earth has radius 1, so altitude (km) is scaled by the Earth's radius.
function toVector3(latDeg, lonDeg, altKm) {
  const radius = 1 + altKm / EARTH_RADIUS_KM;
  const phi = THREE.MathUtils.degToRad(90 - latDeg);
  const theta = THREE.MathUtils.degToRad(lonDeg + 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

function drawOrbit(points) {
  if (orbitLine) {
    scene.remove(orbitLine);
    orbitLine.geometry.dispose();
  }
  const vectors = points.map((p) => toVector3(p.latitude, p.longitude, p.altitude_km));
  orbitLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(vectors),
    new THREE.LineBasicMaterial({ color: 0x5ee1ff })
  );
  scene.add(orbitLine);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});



async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      detail = (await response.json()).detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function showMessage(text) {
  message.textContent = text;
}



let positionTimer = null;
let trackTimer = null;

function stopTracking() {
  clearInterval(positionTimer);
  clearInterval(trackTimer);
  marker.visible = false;
  if (orbitLine) {
    scene.remove(orbitLine);
    orbitLine = null;
  }
}

async function updatePosition(noradId) {
  try {
    const p = await api(`/api/satellites/${noradId}/position`);
    marker.position.copy(toVector3(p.latitude, p.longitude, p.altitude_km));
    marker.visible = true;
    document.getElementById("lat").textContent = `${p.latitude.toFixed(2)}°`;
    document.getElementById("lon").textContent = `${p.longitude.toFixed(2)}°`;
    document.getElementById("alt").textContent = `${p.altitude_km.toFixed(0)} km`;
    document.getElementById("updated").textContent = p.timestamp.slice(11, 19);
    showMessage("");
  } catch (error) {
    showMessage(error.message);
  }
}

async function updateTrack(noradId) {
  try {
    const data = await api(`/api/satellites/${noradId}/track`);
    drawOrbit(data.points);
  } catch (error) {
    showMessage(error.message);
  }
}

function startTracking(noradId) {
  stopTracking();
  updatePosition(noradId);
  updateTrack(noradId);
  positionTimer = setInterval(() => updatePosition(noradId), POSITION_POLL_MS);
  trackTimer = setInterval(() => updateTrack(noradId), TRACK_REFRESH_MS);
}



async function loadSatellites(selectId) {
  const satellites = await api("/api/satellites");
  select.innerHTML = "";
  for (const sat of satellites) {
    const option = document.createElement("option");
    option.value = sat.norad_id;
    option.textContent = `${sat.name} (${sat.norad_id})`;
    select.appendChild(option);
  }
  if (satellites.length === 0) {
    stopTracking();
    showMessage("No satellites yet. Add one by NORAD ID (the ISS is 25544).");
    return;
  }
  if (selectId) select.value = selectId;
  startTracking(select.value);
}

select.addEventListener("change", () => startTracking(select.value));

addForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const noradId = Number(noradInput.value);
  showMessage("Fetching from Celestrak...");
  try {
    await api("/api/satellites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ norad_id: noradId }),
    });
    noradInput.value = "";
    await loadSatellites(String(noradId));
  } catch (error) {
    showMessage(error.message);
  }
});

removeBtn.addEventListener("click", async () => {
  if (!select.value) return;
  try {
    await api(`/api/satellites/${select.value}`, { method: "DELETE" });
    await loadSatellites();
  } catch (error) {
    showMessage(error.message);
  }
});

loadSatellites().catch((error) => showMessage(error.message));