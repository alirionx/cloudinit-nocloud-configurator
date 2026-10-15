/** FR-013: password hashes in crypt format ($id$...$hash) are replaced by asterisks. */
export function maskSecrets(text: string): string {
  return text.replace(/\$(?:1|2[abxy]?|5|6|y|gy|7)\$[^\s'"]+/g, '********')
}
