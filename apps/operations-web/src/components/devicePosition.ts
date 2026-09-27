/** One reading of the device position, never a watch: PHASE_07.md forbids continuous tracking. */
/** The device position, read once on request; `null` when refused or unavailable. */
export function currentPosition(): Promise<{ latitude: number; longitude: number; accuracy: number } | null> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) { resolve(null); return; }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy: position.coords.accuracy }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  });
}
