const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8080";

async function parseJsonOrThrow(response) {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }
  return response.json();
}

const EXTENSION_BY_MIME_TYPE = [
  ["webm", "webm"],
  ["ogg", "ogg"],
  ["mp4", "mp4"],
  ["wav", "wav"],
];

function extensionForBlob(blob) {
  const type = blob.type || "";
  const match = EXTENSION_BY_MIME_TYPE.find(([needle]) => type.includes(needle));
  return match ? match[1] : "webm";
}

export async function transcribeAudio(blob) {
  const form = new FormData();
  form.append("audio", blob, `recording.${extensionForBlob(blob)}`);
  const response = await fetch(`${API_BASE_URL}/transcribe`, { method: "POST", body: form });
  return parseJsonOrThrow(response);
}

export async function runQuery(transcript, history = []) {
  const response = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript, history }),
  });
  return parseJsonOrThrow(response);
}

export async function speak(text) {
  const response = await fetch(`${API_BASE_URL}/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }
  return response.blob();
}
