// src/utils/text.js
export function cleanSpecies(label = "") {
  if (label.startsWith("(") && label.endsWith(")")) {
    return label.slice(1, -1)
  }
  return label
}
