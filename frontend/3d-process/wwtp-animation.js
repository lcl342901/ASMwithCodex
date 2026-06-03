function animateParticleGroup(group) {
  if (!group.visible) return;
  group.children.forEach((particles) => {
    if (!particles.userData.curve) return;
    const position = particles.geometry.attributes.position;
    const { curve, phases, speed } = particles.userData;
    for (let i = 0; i < phases.length; i += 1) {
      phases[i] = (phases[i] + speed * 0.01) % 1;
      const p = curve.getPoint(phases[i]);
      position.setXYZ(i, p.x, p.y, p.z);
    }
    position.needsUpdate = true;
  });
}

function animateAerationBubbles(group, time) {
  if (!group.visible) return;
  group.children.forEach((item) => {
    if (!item.userData.seeds) return;
    const position = item.geometry.attributes.position;
    item.userData.seeds.forEach((seed, i) => {
      const y = 1 + ((time * 0.00055 * seed.rise + seed.offset) % 4.6);
      const sway = Math.sin(time * 0.002 + seed.offset) * 0.12;
      position.setXYZ(i, seed.x + sway, y, seed.z);
    });
    position.needsUpdate = true;
  });
}

function animateWaterSurfaces({ waterSurfaces, flowObjects, timelinePlaying, pulse, time, clamp }) {
  if (!flowObjects.visible) return;
  Object.values(waterSurfaces).forEach((water, index) => {
    const phase = time * 0.004 + index * 0.75;
    water.position.y = water.userData.baseY + Math.sin(phase) * (timelinePlaying ? 0.09 : 0.025);
    water.material.opacity = clamp((water.userData.visualOpacity || 0.55) + pulse * 0.12, 0.25, 0.88);
  });
}

function animateRiskHighlights({ riskHighlights, pulse, clamp }) {
  Object.values(riskHighlights).forEach((highlight) => {
    if (!highlight.visible) return;
    const baseOpacity = highlight.userData.baseOpacity || highlight.material.opacity || 0.25;
    highlight.material.opacity = clamp(baseOpacity + pulse * 0.18, 0.12, 0.7);
  });
}

function animateBlowerRotors(blowerRotors) {
  Object.values(blowerRotors).forEach((rotor) => {
    rotor.rotation.x += rotor.userData.spinSpeed || 0.04;
  });
}

export function createWwtpAnimationController({
  flowObjects,
  bubbleObjects,
  waterSurfaces,
  riskHighlights,
  blowerRotors,
  controls,
  renderer,
  scene,
  camera,
  clamp,
  getTimeline,
  setLastAnimationTime,
  applyTimelineHour
}) {
  return {
    tick(time) {
      const timeline = getTimeline();
      if (timeline.playing) {
        const lastTime = timeline.lastAnimationTime || time;
        const deltaSeconds = Math.min((time - lastTime) / 1000, 0.2);
        const nextHour = timeline.hour + deltaSeconds * timeline.hoursPerSecond;
        setLastAnimationTime(time);
        if (nextHour >= timeline.durationHours) {
          timeline.setPlaying(false);
          applyTimelineHour(timeline.durationHours);
        } else {
          applyTimelineHour(nextHour);
        }
      } else {
        setLastAnimationTime(time);
      }

      const current = getTimeline();
      const pulse = current.playing ? (0.5 + Math.sin(time * 0.009) * 0.5) : 0;
      animateWaterSurfaces({ waterSurfaces, flowObjects, timelinePlaying: current.playing, pulse, time, clamp });
      animateRiskHighlights({ riskHighlights, pulse, clamp });
      animateParticleGroup(flowObjects);
      animateParticleGroup(bubbleObjects);
      animateAerationBubbles(bubbleObjects, time);
      animateBlowerRotors(blowerRotors);

      controls.update();
      renderer.render(scene, camera);
    }
  };
}
