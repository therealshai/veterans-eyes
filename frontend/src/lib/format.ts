export const mmss = (s: number) => {
  const t = Math.max(0, Math.round(s))
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`
}
export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
