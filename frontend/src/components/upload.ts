/** FR-008: text files are kept as text; binary files are Base64-encoded (encoding: b64). */
export function decodeUpload(bytes: Uint8Array): { content: string; encoding: 'text' | 'b64' } {
  try {
    const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
    if (!text.includes('\u0000')) return { content: text, encoding: 'text' }
  } catch {
    // not UTF-8: binary
  }
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return { content: btoa(binary), encoding: 'b64' }
}
