/* BuddyCheck sensor statistics and check-in action rules. */
(function (root) {
  "use strict";
  function features(samples) {
    if (samples.length < 4) throw new Error("BuddyCheck memerlukan empat sampel atau lebih.");
    const deviations = [], angularSteps = [];
    let previousTime = null;
    for (const measurement of samples) {
      if (measurement.accel?.length !== 3 || measurement.gyro?.length !== 3 ||
          ![measurement.time,...measurement.accel,...measurement.gyro].every(Number.isFinite)) {
        throw new Error("Tiga sumbu sensor dan waktu harus berupa angka finite.");
      }
      if (previousTime !== null) {
        const elapsed = measurement.time - previousTime;
        if (elapsed <= 0) throw new Error("Waktu sampel harus bertambah.");
        angularSteps.push(Math.hypot(...measurement.gyro) * elapsed / 1000);
      }
      deviations.push(Math.abs(Math.hypot(...measurement.accel) - 9.81));
      previousTime = measurement.time;
    }
    const sum = (values) => values.reduce((total,value) => total + value,0);
    const round = (value) => Number(value.toFixed(4));
    return {
      motion_rms: round(Math.sqrt(sum(deviations.map((value) => value * value)) / samples.length)),
      rotation_rad: round(sum(angularSteps)), accel_peak: round(Math.max(...deviations)),
      window_ms: Math.round(samples.at(-1).time - samples[0].time),
      sample_count: samples.length,
    };
  }
  function actions(event, actor) {
    if (event.buddy === actor) {
      if (event.status === "CHECK_BUDDY") return ["REQUEST_STATUS"];
      if (event.status === "NO_RESPONSE") return ["REQUEST_STATUS", "ACKNOWLEDGE"];
      if (event.status === "NEED_HELP") return ["ACKNOWLEDGE"];
    }
    if (event.subject === actor && event.status === "AWAITING_REPLY") return ["SAFE", "NEED_HELP"];
    return [];
  }
  const api = { features, actions };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.BuddyCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
