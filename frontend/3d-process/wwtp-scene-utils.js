import * as THREE from "three";

export function addPipe({ scene, clickables, trackStructure, points, material, key, name, radius = 0.28 }) {
  const curve = new THREE.CatmullRomCurve3(points);
  const pipe = new THREE.Mesh(
    new THREE.TubeGeometry(curve, 72, radius, 14, false),
    material
  );
  pipe.castShadow = true;
  pipe.receiveShadow = true;
  pipe.userData = { key, name, curve };
  trackStructure(pipe);
  scene.add(pipe);
  clickables.push(pipe);
  return curve;
}

export function addFlowParticles({ curve, count, color, size, speed, targetGroup, role, registry }) {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  const phases = [];
  for (let i = 0; i < count; i += 1) {
    phases.push(i / count);
    const p = curve.getPoint(phases[i]);
    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y;
    positions[i * 3 + 2] = p.z;
  }
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const particles = new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      color,
      size,
      transparent: true,
      opacity: 0.9,
      depthWrite: false
    })
  );
  particles.userData = { curve, phases, speed, baseSpeed: speed, role };
  targetGroup.add(particles);
  if (role && registry) registry[role] = particles;
  return particles;
}
