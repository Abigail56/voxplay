"use client";

import { useEffect, useRef, useState } from "react";

import type { Clip } from "@/lib/api";

// Browsers support different recording formats; pick the first one available.
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return MIME_TYPES.find((t) => MediaRecorder.isTypeSupported(t));
}

function extensionFor(mime: string): string {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("ogg")) return "ogg";
  if (mime.includes("mp4")) return "m4a";
  return "audio";
}

let counter = 0;
export function makeClip(blob: Blob, filename: string): Clip {
  return { id: `clip-${Date.now()}-${counter++}`, blob, filename, url: URL.createObjectURL(blob) };
}

type Props = {
  onClip: (clip: Clip) => void;
  multiple?: boolean;
  disabled?: boolean;
  allowUpload?: boolean; // false: microphone only (the liveness check wants a live voice)
};

/** Record from the microphone or pick audio files. Calls onClip for each clip. */
export function ClipInput({ onClip, multiple = false, disabled = false, allowUpload = true }: Props) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Stop the microphone if the component unmounts mid-recording.
  useEffect(() => () => stopTracks(), []);

  function stopTracks() {
    if (timerRef.current) clearInterval(timerRef.current);
    recorderRef.current?.stream.getTracks().forEach((t) => t.stop());
  }

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
      recorder.onstop = () => {
        stopTracks();
        const type = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunks, { type });
        onClip(makeClip(blob, `recording-${new Date().toISOString().slice(11, 19)}.${extensionFor(type)}`));
      };
      recorderRef.current = recorder;
      recorder.start();
      setSeconds(0);
      setRecording(true);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (e) {
      setError(
        (e as Error).name === "NotAllowedError"
          ? "Microphone permission was denied."
          : `Cannot start recording: ${(e as Error).message}`,
      );
    }
  }

  function stop() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  function onFiles(e: React.ChangeEvent<HTMLInputElement>) {
    Array.from(e.target.files ?? []).forEach((f) => onClip(makeClip(f, f.name)));
    e.target.value = ""; // allow picking the same file again
  }

  return (
    <div className="clip-input">
      {recording ? (
        <button type="button" className="btn danger" onClick={stop}>
          <span className="dot" /> Stop ({seconds}s)
        </button>
      ) : (
        <button type="button" className="btn" onClick={start} disabled={disabled}>
          Record
        </button>
      )}
      {allowUpload && (
        <label className={`btn ghost ${disabled || recording ? "disabled" : ""}`}>
          Upload file{multiple ? "s" : ""}
          <input type="file" accept="audio/*,.wav,.mp3,.webm,.ogg,.m4a,.flac" multiple={multiple} onChange={onFiles} hidden disabled={disabled || recording} />
        </label>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
