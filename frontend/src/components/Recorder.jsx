import { useRef, useState } from "react";

// Mic capture (record/upload) — the UI's entry point, per the top-level
// README's User Interface feature list.
export default function Recorder({ onAudioReady, disabled }) {
  const [isRecording, setIsRecording] = useState(false);
  const [micError, setMicError] = useState(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const stopRequestedRef = useRef(false);

  // Chunk interval for MediaRecorder's `timeslice` — without it, the browser
  // only emits one `dataavailable` event, right when `.stop()` fires. Buffering
  // in intervals instead means each earlier chunk is already flushed out of the
  // encoder's internal buffer well before the user stops talking, instead of
  // sitting unflushed until the end.
  const CHUNK_INTERVAL_MS = 250;
  // getUserMedia's stream needs a moment to settle (mic gain/echo-cancellation
  // ramp-up) before it's actually capturing clean audio — starting the recorder
  // immediately reliably clips the first fraction of a second of speech, which
  // is exactly the "misses part of what I said" symptom. This is a well-known
  // MediaRecorder gotcha, not specific to this app.
  const MIC_WARMUP_MS = 300;

  // Chrome/Firefox/Safari each support a different subset of container/codec
  // combos for MediaRecorder — asking for one explicitly (instead of letting
  // the browser pick silently) means we know exactly what we got back and can
  // label the Blob correctly, rather than assuming "audio/webm" and shipping
  // a file whose declared type doesn't match its actual bytes.
  const CANDIDATE_MIME_TYPES = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];

  function pickSupportedMimeType() {
    return CANDIDATE_MIME_TYPES.find(
      (type) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported?.(type)
    );
  }

  async function startRecording() {
    setMicError(null);
    stopRequestedRef.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setIsRecording(true); // update the button immediately; actual capture starts after warmup below

      await new Promise((resolve) => setTimeout(resolve, MIC_WARMUP_MS));

      // Stop was clicked during the warmup window, before the recorder below
      // even existed — release the stream now instead of leaving the mic
      // running with nothing left able to stop it.
      if (stopRequestedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      const mimeType = pickSupportedMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        // recorder.mimeType reflects what the browser actually recorded,
        // which may differ from what we requested above.
        onAudioReady(new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" }));
      };
      recorder.start(CHUNK_INTERVAL_MS);
      mediaRecorderRef.current = recorder;
    } catch {
      setIsRecording(false);
      setMicError("Couldn't access the microphone — check browser permissions, or upload a file instead.");
    }
  }

  function stopRecording() {
    stopRequestedRef.current = true;
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (file) onAudioReady(file);
    event.target.value = "";
  }

  return (
    <div className="recorder">
      <button
        type="button"
        className={isRecording ? "btn btn-recording" : "btn btn-primary"}
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled}
      >
        {isRecording ? <><span className="rec-dot" />Stop recording</> : "Record"}
      </button>
      <label className={`btn btn-secondary file-upload ${disabled ? "btn-disabled" : ""}`}>
        Upload audio
        <input type="file" accept="audio/*" onChange={handleFileChange} disabled={disabled} hidden />
      </label>
      {micError && <p className="error">{micError}</p>}
    </div>
  );
}
