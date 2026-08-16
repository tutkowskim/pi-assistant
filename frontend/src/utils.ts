export function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function isTerminalRun(status: string): boolean {
  return ['succeeded', 'review_failed', 'failed', 'cancelled'].includes(status)
}
