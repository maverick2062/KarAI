let sharedAudioContext: AudioContext | null = null;

export function playNotificationSound(): void {
  try {
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;

    if (!sharedAudioContext || sharedAudioContext.state === "closed") {
      sharedAudioContext = new AudioContextClass();
    }

    if (sharedAudioContext.state === "suspended") {
      void sharedAudioContext.resume();
    }

    const now = sharedAudioContext.currentTime;
    // macOS-inspired gentle two-tone glass chime (D5 -> A5)
    for (const [frequency, startOffset, duration] of [
      [587.33, 0, 0.18],
      [880.0, 0.08, 0.28],
    ] as const) {
      const oscillator = sharedAudioContext.createOscillator();
      const gain = sharedAudioContext.createGain();

      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(frequency, now + startOffset);

      gain.gain.setValueAtTime(0.2, now + startOffset);
      gain.gain.exponentialRampToValueAtTime(0.001, now + startOffset + duration);

      oscillator.connect(gain);
      gain.connect(sharedAudioContext.destination);

      oscillator.start(now + startOffset);
      oscillator.stop(now + startOffset + duration);
    }
  } catch (err) {
    console.warn("Could not play notification sound:", err);
  }
}
