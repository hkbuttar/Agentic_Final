import { useRef, useState } from "react";

// Mic capture (record/upload) — the UI's entry point, per the top-level
// README's User Interface feature list.
export default function Recorder({ onAudioReady, disabled }) {
  const [isRecording, setIsRecording] = useState(false);
  const [micError, setMicError] = useState(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  async function startRecording() {
    setMicError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        onAudioReady(new Blob(chunksRef.current, { type: "audio/webm" }));
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch {
      setMicError("Couldn't access the microphone — check browser permissions, or upload a file instead.");
    }
  }

  function stopRecording() {
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
        {isRecording ? "⏹ Stop Recording" : "🎙 Record"}
      </button>
      <label className={`btn btn-secondary file-upload ${disabled ? "btn-disabled" : ""}`}>
        Upload audio
        <input type="file" accept="audio/*" onChange={handleFileChange} disabled={disabled} hidden />
      </label>
      {micError && <p className="error">{micError}</p>}
    </div>
  );
}
